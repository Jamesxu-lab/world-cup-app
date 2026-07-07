"""
比赛和叙事 API 路由
"""
from datetime import date as date_cls, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, selectinload
from app.core.config import get_settings
from app.core.database import get_db
from app.models.match import Match, Narrative
from app.services.hooks import generate_hook
from app.services.fallback_narrative import (
    STYLE_NAMES,
    build_fallback_narrative,
    get_local_narrative_model_version,
    is_local_narrative_model,
)
from app.services.startup_match_sync import (
    get_today_date,
    sync_match_details_if_stale,
    sync_product_date_if_stale,
    sync_recent_completed_product_dates,
)
from app.i18n import get_team_cn, get_stadium_cn, get_city_cn, get_round_cn, get_status_cn

router = APIRouter(prefix="/api/v1", tags=["matches"])

COMPLETED_STATUSES = ("FT", "AET", "PEN")
DETAIL_SYNC_STATUSES = ("1H", "2H", "HT", "ET", "BT", "P", "SUSP", "INT", *COMPLETED_STATUSES)
WORLD_CUP_2026_START = datetime(2026, 1, 1)
WORLD_CUP_2026_END = datetime(2027, 1, 1)


@router.get("/matches")
async def list_matches(
    date: str = Query(None, description="日期，格式 YYYY-MM-DD，不传则返回当天"),
    include_unfinished: bool = Query(False, description="是否包含未开始/进行中的比赛"),
    db: Session = Depends(get_db),
):
    """获取比赛列表，每场带比分和一句话钩子"""
    target_date = date or get_today_date()
    try:
        start, end = get_product_day_utc_range(target_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD") from exc

    settings = get_settings()
    if target_date == get_today_date():
        try:
            await sync_product_date_if_stale(
                target_date,
                with_details=settings.sync_startup_with_details,
            )
        except Exception:
            # 列表接口不能因为外部数据源短暂失败而不可用，继续返回本地已有数据。
            pass

    query = build_match_query(db)
    query = query.filter(Match.match_date >= start, Match.match_date < end)

    if not include_unfinished:
        query = query.filter(Match.status.in_(COMPLETED_STATUSES))

    matches = query.order_by(Match.match_date.desc()).all()

    return {
        "matches": [serialize_match_summary(match) for match in matches],
        "count": len(matches),
        "date": target_date,
        "include_unfinished": include_unfinished,
    }


@router.get("/matches/history")
async def list_match_history(
    limit: int = Query(6, ge=1, le=6, description="最多返回多少场历史完赛"),
    offset: int = Query(0, ge=0, description="从第几场开始返回"),
    db: Session = Depends(get_db),
):
    """获取今天之前的历史完赛列表。"""
    settings = get_settings()
    await sync_recent_completed_product_dates(
        days=3,
        with_details=settings.sync_startup_with_details,
    )

    today_start, _ = get_product_day_utc_range(get_today_date())
    base_query = (
        build_match_query(db)
        .filter(Match.status.in_(COMPLETED_STATUSES))
        .filter(Match.match_date < today_start)
    )
    total = base_query.count()
    matches = (
        base_query
        .order_by(Match.match_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    next_offset = offset + len(matches)

    return {
        "matches": [serialize_match_summary(match) for match in matches],
        "count": len(matches),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": next_offset < total,
        "next_offset": next_offset if next_offset < total else None,
    }


@router.get("/matches/{match_id}")
async def get_match(
    match_id: str,
    db: Session = Depends(get_db),
):
    """获取单场比赛详情"""
    match = db.query(Match).options(
        selectinload(Match.events),
        selectinload(Match.stats),
        selectinload(Match.performances),
        selectinload(Match.narratives),
    ).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    if await _sync_missing_match_details(db, match):
        match = db.query(Match).options(
            selectinload(Match.events),
            selectinload(Match.stats),
            selectinload(Match.performances),
            selectinload(Match.narratives),
        ).filter(Match.id == match_id).first()

    # 事件（按时间排序）
    events = []
    for evt in sorted(match.events, key=lambda e: (e.minute, e.extra_minute or 0)):
        events.append({
            "minute": evt.minute,
            "extra_minute": evt.extra_minute,
            "event_type": evt.event_type,
            "detail": evt.detail,
            "player_name": evt.player_name,
            "team": get_team_cn(evt.team),
            "assist_player": evt.assist_player,
        })

    # 统计
    stats = {}
    for stat in match.stats:
        stat_name = stat.stat_type
        if stat_name not in stats:
            stats[stat_name] = {}
        stats[stat_name][get_team_cn(stat.team)] = stat.stat_value

    # 球员 TOP10
    players = sorted(match.performances, key=lambda p: (p.rating or 0, p.goals or 0), reverse=True)
    top_players = []
    for p in players[:10]:
        top_players.append({
            "name": p.player_name,
            "team": get_team_cn(p.team),
            "position": p.position,
            "rating": p.rating,
            "goals": p.goals,
            "assists": p.assists,
        })

    # 可用风格
    available_styles = list(set(n.style for n in match.narratives))

    return {
        "id": match.id,
        "fixture_id": match.fixture_id,
        "home_team": get_team_cn(match.home_team),
        "away_team": get_team_cn(match.away_team),
        "home_score": match.home_score,
        "away_score": match.away_score,
        "match_date": str(match.match_date),
        "match_day": get_product_day(match.match_date),
        "round": get_round_cn(match.round) if match.round else "",
        "group_name": match.group_name or "",
        "stadium": get_stadium_cn(match.stadium) if match.stadium else "",
        "city": get_city_cn(match.city) if match.city else "",
        "status": get_status_cn(match.status),
        "status_code": match.status,
        "hook": generate_hook(match),
        "events": events,
        "stats": stats,
        "top_players": top_players,
        "available_styles": available_styles,
    }


def build_match_query(db: Session):
    """Build the common 2026 World Cup match list query."""
    return (
        db.query(Match)
        .options(
            selectinload(Match.events),
            selectinload(Match.performances),
            selectinload(Match.narratives),
        )
        .filter(
            Match.match_date >= WORLD_CUP_2026_START,
            Match.match_date < WORLD_CUP_2026_END,
        )
    )


def get_product_day_utc_range(date_str: str) -> tuple[datetime, datetime]:
    """Convert a product calendar day into the UTC range stored in SQLite."""
    target = date_cls.fromisoformat(date_str)
    settings = get_settings()
    try:
        tz = ZoneInfo(settings.app_timezone)
    except ZoneInfoNotFoundError:
        start = datetime.combine(target, time.min)
        return start, start + timedelta(days=1)

    local_start = datetime.combine(target, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return utc_start, utc_end


def get_product_day(match_date: datetime) -> str:
    """Return the product calendar day for a stored match datetime."""
    settings = get_settings()
    try:
        tz = ZoneInfo(settings.app_timezone)
    except ZoneInfoNotFoundError:
        return match_date.date().isoformat()

    if match_date.tzinfo is None:
        match_date = match_date.replace(tzinfo=timezone.utc)
    return match_date.astimezone(tz).date().isoformat()


def serialize_match_summary(match: Match) -> dict:
    return {
        "id": match.id,
        "fixture_id": match.fixture_id,
        "home_team": get_team_cn(match.home_team),
        "away_team": get_team_cn(match.away_team),
        "home_score": match.home_score,
        "away_score": match.away_score,
        "match_date": str(match.match_date),
        "match_day": get_product_day(match.match_date),
        "round": get_round_cn(match.round) if match.round else "",
        "group_name": match.group_name or "",
        "stadium": get_stadium_cn(match.stadium) if match.stadium else "",
        "status": get_status_cn(match.status),
        "status_code": match.status,
        "hook": generate_hook(match),
        "available_styles": list(set(n.style for n in match.narratives)),
    }


@router.get("/matches/{match_id}/narrative")
async def get_narrative(
    match_id: str,
    style: str = Query("formal", description="叙事风格: formal / funny / tactical"),
    db: Session = Depends(get_db),
):
    """获取某场比赛某种风格的叙事卡片"""
    match = db.query(Match).options(
        selectinload(Match.events),
        selectinload(Match.stats),
        selectinload(Match.performances),
    ).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    if await _sync_missing_match_details(db, match):
        match = db.query(Match).options(
            selectinload(Match.events),
            selectinload(Match.stats),
            selectinload(Match.performances),
        ).filter(Match.id == match_id).first()

    narratives = db.query(Narrative).filter(
        Narrative.match_id == match_id,
        Narrative.style == style,
    ).order_by(Narrative.card_index).all()

    if _should_refresh_local_narratives(match, narratives):
        db.query(Narrative).filter(
            Narrative.match_id == match_id,
            Narrative.style == style,
        ).delete(synchronize_session=False)
        for i, card in enumerate(build_fallback_narrative(match, style), start=1):
            db.add(Narrative(
                match_id=match_id,
                style=style,
                card_index=i,
                card_type=card.get("card_type"),
                title=card.get("title"),
                content=card.get("content"),
                model_version=get_local_narrative_model_version(match),
            ))
        db.commit()
        narratives = db.query(Narrative).filter(
            Narrative.match_id == match_id,
            Narrative.style == style,
        ).order_by(Narrative.card_index).all()

    if narratives:
        cards = []
        for n in narratives:
            cards.append({
                "card_index": n.card_index,
                "card_type": n.card_type,
                "title": n.title,
                "content": n.content,
            })
    else:
        cards = [
            {"card_index": i + 1, **card}
            for i, card in enumerate(build_fallback_narrative(match, style))
        ]

    return {
        "match_id": match_id,
        "style": style,
        "style_name": STYLE_NAMES.get(style, style),
        "cards": cards,
        "card_count": len(cards),
    }


def _should_refresh_local_narratives(match: Match, narratives: list[Narrative]) -> bool:
    if not narratives:
        return False
    if not all(is_local_narrative_model(n.model_version) for n in narratives):
        return False
    current_version = get_local_narrative_model_version(match)
    return any(n.model_version != current_version for n in narratives)


def _has_match_details(match: Match) -> bool:
    return bool(match.events or match.stats or match.performances)


def _should_attempt_detail_sync(match: Match) -> bool:
    return match.status in DETAIL_SYNC_STATUSES and not _has_match_details(match)


async def _sync_missing_match_details(db: Session, match: Match) -> bool:
    if not _should_attempt_detail_sync(match):
        return False
    try:
        return await sync_match_details_if_stale(db, match)
    except Exception:
        # Detail data improves the report, but the page should still render from
        # the latest score if the external feed is temporarily unavailable.
        return False

"""
比赛和叙事 API 路由
"""
from datetime import date as date_cls, datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, selectinload
from app.core.database import get_db
from app.models.match import Match, Narrative
from app.services.hooks import generate_hook
from app.services.fallback_narrative import STYLE_NAMES, build_fallback_narrative
from app.i18n import get_team_cn, get_stadium_cn, get_city_cn, get_round_cn, get_status_cn

router = APIRouter(prefix="/api/v1", tags=["matches"])

COMPLETED_STATUSES = ("FT", "AET", "PEN")


@router.get("/matches")
async def list_matches(
    date: str = Query(None, description="日期，格式 YYYY-MM-DD，不传则返回当天"),
    include_unfinished: bool = Query(False, description="是否包含未开始/进行中的比赛"),
    db: Session = Depends(get_db),
):
    """获取比赛列表，每场带比分和一句话钩子"""
    query = db.query(Match).options(
        selectinload(Match.events),
        selectinload(Match.performances),
        selectinload(Match.narratives),
    )

    # 当前产品只展示 2026 世界杯数据，历史测试数据保留在库中但不出现在列表。
    query = query.filter(
        Match.match_date >= datetime(2026, 1, 1),
        Match.match_date < datetime(2027, 1, 1),
    )

    target_date = date or date_cls.today().isoformat()
    try:
        start = datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD") from exc

    end = start + timedelta(days=1)
    query = query.filter(Match.match_date >= start, Match.match_date < end)

    if not include_unfinished:
        query = query.filter(Match.status.in_(COMPLETED_STATUSES))

    matches = query.order_by(Match.match_date.desc()).all()

    result = []
    for match in matches:
        result.append({
            "id": match.id,
            "fixture_id": match.fixture_id,
            "home_team": get_team_cn(match.home_team),
            "away_team": get_team_cn(match.away_team),
            "home_score": match.home_score,
            "away_score": match.away_score,
            "match_date": str(match.match_date),
            "round": get_round_cn(match.round) if match.round else "",
            "group_name": match.group_name or "",
            "stadium": get_stadium_cn(match.stadium) if match.stadium else "",
            "status": get_status_cn(match.status),
            "hook": generate_hook(match),
            "available_styles": list(set(n.style for n in match.narratives)),
        })

    return {
        "matches": result,
        "count": len(result),
        "date": target_date,
        "include_unfinished": include_unfinished,
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
        "round": get_round_cn(match.round) if match.round else "",
        "group_name": match.group_name or "",
        "stadium": get_stadium_cn(match.stadium) if match.stadium else "",
        "city": get_city_cn(match.city) if match.city else "",
        "status": get_status_cn(match.status),
        "hook": generate_hook(match),
        "events": events,
        "stats": stats,
        "top_players": top_players,
        "available_styles": available_styles,
    }


@router.get("/matches/{match_id}/narrative")
async def get_narrative(
    match_id: str,
    style: str = Query("formal", description="叙事风格: formal / funny / tactical"),
    db: Session = Depends(get_db),
):
    """获取某场比赛某种风格的叙事卡片"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

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

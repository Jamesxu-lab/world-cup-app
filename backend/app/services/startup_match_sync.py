"""
Startup match synchronization helpers.
"""
import logging
from datetime import date as date_cls, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.match import Match
from app.services.data_ingestion import save_match_to_db
from app.services.football_api import FootballAPI, FootballAPIError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
_last_product_date_sync: dict[str, datetime] = {}
_last_fixture_detail_sync: dict[int, datetime] = {}


def get_yesterday_date() -> str:
    """Return yesterday in the configured product timezone."""
    return get_relative_product_date(-1)


def get_today_date() -> str:
    """Return today in the configured product timezone."""
    return get_relative_product_date(0)


def get_product_timezone():
    """Return the configured product timezone, falling back to local time."""
    settings = get_settings()
    try:
        return ZoneInfo(settings.app_timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown app timezone %s, falling back to local time", settings.app_timezone)
        return None


def get_relative_product_date(offset_days: int) -> str:
    """Return a relative date in the configured product timezone."""
    tz = get_product_timezone()
    now = datetime.now(tz) if tz else datetime.now()
    return (now + timedelta(days=offset_days)).date().isoformat()


def get_recent_completed_product_dates(days: int = 3) -> list[str]:
    """Return recent product dates before today, newest first."""
    if days < 1:
        return []

    today = date_cls.fromisoformat(get_today_date())
    return [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(1, days + 1)
    ]


def get_api_dates_for_product_date(date_str: str) -> list[str]:
    """
    Return API-Football date values that overlap one product calendar day.

    Match times are stored from API UTC timestamps, while the product day is
    Asia/Shanghai by default. A local day can span two UTC dates, so syncing only
    the local date misses early-morning or late-night fixtures.
    """
    target = date_cls.fromisoformat(date_str)
    tz = get_product_timezone()
    if not tz:
        return [date_str]

    local_start = datetime.combine(target, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1) - timedelta(microseconds=1)
    utc_start = local_start.astimezone(timezone.utc).date()
    utc_end = local_end.astimezone(timezone.utc).date()

    api_dates = []
    current = utc_start
    while current <= utc_end:
        api_dates.append(current.isoformat())
        current += timedelta(days=1)
    return api_dates


async def sync_worldcup_matches_for_date(date_str: str, *, with_details: bool = False) -> int:
    """Fetch World Cup fixtures for one date and upsert them into the local DB."""
    api = FootballAPI()
    fixtures = await api.get_worldcup_fixtures_by_date(date_str)

    db = SessionLocal()
    try:
        for fixture in fixtures:
            match_data = {"events": [], "statistics": [], "players": [], "lineups": []}
            if with_details:
                try:
                    match_data = await api.get_full_match_data(fixture["fixture"]["id"])
                except Exception as exc:
                    logger.warning(
                        "Match detail sync failed for fixture %s: %s",
                        fixture.get("fixture", {}).get("id"),
                        exc,
                    )

            save_match_to_db(db, fixture, match_data)
    finally:
        db.close()

    return len(fixtures)


async def sync_worldcup_matches_for_product_date(date_str: str, *, with_details: bool = False) -> int:
    """Sync every API date needed to cover one product calendar day."""
    total = 0
    seen_fixture_ids: set[int] = set()

    for api_date in get_api_dates_for_product_date(date_str):
        api = FootballAPI()
        fixtures = await api.get_worldcup_fixtures_by_date(api_date)
        db = SessionLocal()
        try:
            for fixture in fixtures:
                fixture_id = fixture["fixture"]["id"]
                if fixture_id in seen_fixture_ids:
                    continue
                seen_fixture_ids.add(fixture_id)

                match_data = {"events": [], "statistics": [], "players": [], "lineups": []}
                if with_details:
                    try:
                        match_data = await api.get_full_match_data(fixture_id)
                    except Exception as exc:
                        logger.warning("Match detail sync failed for fixture %s: %s", fixture_id, exc)

                save_match_to_db(db, fixture, match_data)
                total += 1
        finally:
            db.close()

    return total


async def sync_product_date_if_stale(
    date_str: str,
    *,
    with_details: bool = False,
    ttl_seconds: int | None = None,
) -> int:
    """Best-effort throttled sync for a product date."""
    settings = get_settings()
    if not settings.api_football_key:
        logger.info("Match sync skipped for %s: API_FOOTBALL_KEY is empty", date_str)
        return 0

    ttl = settings.match_list_sync_ttl_seconds if ttl_seconds is None else ttl_seconds
    now = datetime.now(timezone.utc)
    last_sync = _last_product_date_sync.get(date_str)
    if last_sync and (now - last_sync).total_seconds() < ttl:
        return 0

    count = await sync_worldcup_matches_for_product_date(date_str, with_details=with_details)
    _last_product_date_sync[date_str] = now
    logger.info("Synced %s World Cup fixtures for product date %s", count, date_str)
    return count


async def sync_match_details_if_stale(
    db: Session,
    match: Match,
    *,
    ttl_seconds: int | None = None,
) -> bool:
    """Best-effort throttled detail sync for one started or completed fixture."""
    settings = get_settings()
    if not settings.api_football_key:
        logger.info("Match detail sync skipped for fixture %s: API_FOOTBALL_KEY is empty", match.fixture_id)
        return False

    ttl = settings.match_list_sync_ttl_seconds if ttl_seconds is None else ttl_seconds
    now = datetime.now(timezone.utc)
    last_sync = _last_fixture_detail_sync.get(match.fixture_id)
    if last_sync and (now - last_sync).total_seconds() < ttl:
        return False

    api = FootballAPI()
    fixture = await api.get_fixture_by_id(match.fixture_id)
    if not fixture:
        logger.info("Match detail sync skipped: fixture %s not found", match.fixture_id)
        _last_fixture_detail_sync[match.fixture_id] = now
        return False

    match_data = await api.get_full_match_data(match.fixture_id)
    save_match_to_db(db, fixture, match_data)
    _last_fixture_detail_sync[match.fixture_id] = now
    logger.info("Synced detail data for fixture %s", match.fixture_id)
    return True


async def sync_recent_completed_product_dates(
    *,
    days: int = 3,
    with_details: bool = False,
) -> dict[str, int]:
    """Best-effort sync for recent completed product dates used by history."""
    results: dict[str, int] = {}
    for date_str in get_recent_completed_product_dates(days):
        try:
            results[date_str] = await sync_product_date_if_stale(
                date_str,
                with_details=with_details,
            )
        except FootballAPIError as exc:
            results[date_str] = 0
            logger.warning("Recent match sync failed for %s: %s", date_str, exc)
        except Exception:
            results[date_str] = 0
            logger.exception("Unexpected recent match sync failure for %s", date_str)
    return results


async def sync_yesterday_matches_on_startup() -> None:
    """Best-effort startup sync for recent World Cup fixtures."""
    settings = get_settings()
    if not settings.sync_yesterday_on_startup:
        logger.info("Startup match sync disabled")
        return

    if not settings.api_football_key:
        logger.warning("Startup match sync skipped: API_FOOTBALL_KEY is empty")
        return

    dates = [get_yesterday_date()]
    if settings.sync_today_on_startup:
        today = get_today_date()
        if today not in dates:
            dates.append(today)

    for date_str in dates:
        try:
            count = await sync_product_date_if_stale(
                date_str,
                with_details=settings.sync_startup_with_details,
                ttl_seconds=0,
            )
            logger.info("Startup synced %s World Cup matches for product date %s", count, date_str)
        except FootballAPIError as exc:
            logger.warning("Startup match sync failed for %s: %s", date_str, exc)
        except Exception:
            logger.exception("Unexpected startup match sync failure for %s", date_str)

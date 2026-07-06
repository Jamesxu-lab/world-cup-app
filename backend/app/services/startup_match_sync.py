"""
Startup match synchronization helpers.
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.data_ingestion import save_match_to_db
from app.services.football_api import FootballAPI, FootballAPIError

logger = logging.getLogger(__name__)


def get_yesterday_date() -> str:
    """Return yesterday in the configured product timezone."""
    settings = get_settings()
    try:
        tz = ZoneInfo(settings.app_timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown app timezone %s, falling back to local time", settings.app_timezone)
        return (datetime.now() - timedelta(days=1)).date().isoformat()

    return (datetime.now(tz) - timedelta(days=1)).date().isoformat()


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


async def sync_yesterday_matches_on_startup() -> None:
    """Best-effort startup sync for yesterday's World Cup fixtures."""
    settings = get_settings()
    if not settings.sync_yesterday_on_startup:
        logger.info("Startup yesterday match sync disabled")
        return

    if not settings.api_football_key:
        logger.warning("Startup yesterday match sync skipped: API_FOOTBALL_KEY is empty")
        return

    date_str = get_yesterday_date()
    try:
        count = await sync_worldcup_matches_for_date(
            date_str,
            with_details=settings.sync_startup_with_details,
        )
        logger.info("Startup synced %s World Cup matches for %s", count, date_str)
    except FootballAPIError as exc:
        logger.warning("Startup yesterday match sync failed for %s: %s", date_str, exc)
    except Exception:
        logger.exception("Unexpected startup yesterday match sync failure for %s", date_str)

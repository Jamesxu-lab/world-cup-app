"""
Prediction snapshot synchronization helpers.

The web app should keep serving even when upstream football data sources are
slow or temporarily unavailable, so startup sync is best-effort by default.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings
from app.services.prediction_model import SNAPSHOT_PATH
from scripts.sync_prediction_data import build_snapshot, validate_snapshot


logger = logging.getLogger(__name__)


def _parse_snapshot_updated_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_snapshot_updated_at() -> datetime | None:
    """Return the snapshot timestamp, falling back to file mtime when needed."""
    if not SNAPSHOT_PATH.exists():
        return None

    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    updated_at = _parse_snapshot_updated_at(payload.get("updated_at"))
    if updated_at:
        return updated_at.astimezone(timezone.utc)

    try:
        return datetime.fromtimestamp(SNAPSHOT_PATH.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def prediction_snapshot_is_stale(*, max_age_hours: int | None = None, now: datetime | None = None) -> bool:
    """Check whether prediction inputs should be refreshed."""
    settings = get_settings()
    max_age = settings.prediction_sync_max_age_hours if max_age_hours is None else max_age_hours
    updated_at = get_snapshot_updated_at()
    if updated_at is None:
        return True
    if max_age <= 0:
        return False

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return reference.astimezone(timezone.utc) - updated_at > timedelta(hours=max_age)


def _configured_injuries_path() -> Path | None:
    value = get_settings().prediction_sync_injuries_path.strip()
    return Path(value) if value else None


def sync_prediction_snapshot(*, injuries_path: Path | None = None) -> dict:
    """Build and atomically write the local prediction input snapshot."""
    snapshot = build_snapshot(injuries_path)
    validation_errors = validate_snapshot(snapshot)
    if validation_errors:
        raise ValueError("Snapshot validation failed: " + "; ".join(validation_errors))

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = SNAPSHOT_PATH.with_suffix(SNAPSHOT_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(SNAPSHOT_PATH)
    logger.info(
        "Prediction snapshot synced: teams=%s fixtures=%s updated_at=%s",
        len(snapshot.get("teams", [])),
        len(snapshot.get("fixtures", [])),
        snapshot.get("updated_at"),
    )
    return snapshot


async def sync_prediction_snapshot_if_stale(*, force: bool = False) -> bool:
    """Refresh prediction inputs when stale. Returns True when a sync ran."""
    if not force and not prediction_snapshot_is_stale():
        logger.info("Prediction snapshot sync skipped: snapshot is fresh")
        return False

    try:
        await asyncio.to_thread(sync_prediction_snapshot, injuries_path=_configured_injuries_path())
    except Exception:
        logger.exception("Prediction snapshot sync failed")
        return False
    return True


async def sync_prediction_snapshot_on_startup() -> asyncio.Task | None:
    """Best-effort startup sync. Background by default so app boot stays fast."""
    settings = get_settings()
    if not settings.prediction_sync_on_startup:
        logger.info("Startup prediction snapshot sync disabled")
        return None

    if settings.prediction_sync_block_startup:
        await sync_prediction_snapshot_if_stale()
        return None

    task = asyncio.create_task(sync_prediction_snapshot_if_stale())
    task.add_done_callback(_log_background_task_failure)
    return task


def _daily_sync_time() -> time:
    raw = get_settings().prediction_sync_daily_time.strip()
    try:
        hour, minute = raw.split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except (ValueError, TypeError):
        logger.warning("Invalid PREDICTION_SYNC_DAILY_TIME=%s, falling back to 10:00", raw)
        return time(hour=10, minute=0)


def _app_timezone() -> ZoneInfo:
    timezone_name = get_settings().app_timezone
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown app timezone %s, falling back to UTC", timezone_name)
        return ZoneInfo("UTC")


def seconds_until_next_daily_sync(now: datetime | None = None) -> float:
    """Return seconds until the next configured daily sync time."""
    tz = _app_timezone()
    reference = now.astimezone(tz) if now else datetime.now(tz)
    configured_time = _daily_sync_time()
    target = datetime.combine(reference.date(), configured_time, tzinfo=tz)
    if target <= reference:
        target += timedelta(days=1)
    return (target - reference).total_seconds()


async def run_prediction_daily_sync_loop() -> None:
    """Run prediction sync once per day until cancelled."""
    while True:
        delay = seconds_until_next_daily_sync()
        logger.info("Next prediction snapshot daily sync in %.0f seconds", delay)
        await asyncio.sleep(delay)
        await sync_prediction_snapshot_if_stale(force=True)


def start_prediction_daily_sync_task() -> asyncio.Task | None:
    settings = get_settings()
    if not settings.prediction_sync_daily_enabled:
        logger.info("Daily prediction snapshot sync disabled")
        return None

    task = asyncio.create_task(run_prediction_daily_sync_loop())
    task.add_done_callback(_log_background_task_failure)
    return task


def _log_background_task_failure(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    try:
        task.result()
    except Exception:
        logger.exception("Prediction sync background task crashed")

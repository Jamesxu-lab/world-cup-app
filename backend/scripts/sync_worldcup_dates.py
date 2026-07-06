"""
同步指定日期的世界杯比赛数据。

用法:
  cd backend
  .venv/bin/python scripts/sync_worldcup_dates.py 2026-06-17 2026-06-18
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import SessionLocal, init_db
from app.services.football_api import FootballAPI
from app.services.data_ingestion import save_match_to_db


async def sync_dates(dates: list[str], season: int | None, with_details: bool) -> None:
    api = FootballAPI()
    init_db()
    db = SessionLocal()

    try:
        for date_str in dates:
            fixtures = await api.get_worldcup_fixtures_by_date(date_str, season=season)
            print(f"\n{date_str}: 获取到 {len(fixtures)} 场世界杯比赛")

            for fixture in fixtures:
                fixture_id = fixture["fixture"]["id"]
                teams = fixture["teams"]
                goals = fixture["goals"]
                status = fixture["fixture"]["status"]
                title = (
                    f"{teams['home']['name']} {goals.get('home')}-{goals.get('away')} "
                    f"{teams['away']['name']} ({status.get('short')})"
                )
                print(f"  同步 {fixture_id}: {title}")

                match_data = {"events": [], "statistics": [], "players": [], "lineups": []}
                if with_details:
                    try:
                        match_data = await api.get_full_match_data(fixture_id)
                    except Exception as exc:
                        print(f"    明细拉取失败，保留基础赛程/比分: {exc}")

                match = save_match_to_db(db, fixture, match_data)
                print(f"    已入库: {match.home_team} {match.home_score}-{match.away_score} {match.away_team}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="同步指定日期的世界杯比赛数据")
    parser.add_argument("dates", nargs="+", help="日期列表，格式 YYYY-MM-DD")
    parser.add_argument("--season", type=int, default=None, help="可选赛季；免费 API 计划查询 2026 时不要传")
    parser.add_argument("--with-details", action="store_true", help="同时拉取事件、统计、球员明细；会显著增加 API 请求")
    args = parser.parse_args()

    asyncio.run(sync_dates(args.dates, season=args.season, with_details=args.with_details))


if __name__ == "__main__":
    main()

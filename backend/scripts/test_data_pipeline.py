"""
测试脚本：验证数据链路是否跑通
用法: cd backend && python scripts/test_data_pipeline.py

前提：在 .env 中配置有效的 API_FOOTBALL_KEY
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import get_settings
from app.core.database import init_db, SessionLocal
from app.services.football_api import FootballAPI
from app.services.data_ingestion import (
    parse_fixture_to_match,
    parse_events,
    parse_statistics,
    parse_player_performances,
    save_match_to_db,
)


async def test_pipeline():
    settings = get_settings()

    if settings.api_football_key == "your_api_key_here":
        print("❌ 请先在 backend/.env 中配置 API_FOOTBALL_KEY")
        print("   注册地址: https://dashboard.api-football.com/register")
        return

    api = FootballAPI()

    # Step 1: 获取 2022 世界杯比赛列表
    print("=" * 60)
    print("Step 1: 获取 2022 世界杯比赛列表...")
    fixtures = await api.get_worldcup_fixtures(season=2022)
    print(f"  ✓ 获取到 {len(fixtures)} 场比赛")

    # 找一场已完成的比赛（有比分有统计）
    target = None
    for f in fixtures:
        if f["fixture"]["status"]["short"] == "FT" and f["goals"]["home"] is not None:
            target = f
            break

    if not target:
        print("❌ 未找到已完成的比赛")
        return

    match_info = parse_fixture_to_match(target)
    fixture_id = match_info["fixture_id"]
    print(f"\nStep 2: 选择测试比赛: {match_info['home_team']} vs {match_info['away_team']} (ID: {fixture_id})")

    # Step 3: 拉取完整数据
    print("\nStep 3: 拉取完整比赛数据（事件+统计+球员）...")
    full_data = await api.get_full_match_data(fixture_id)

    events = parse_events(full_data.get("events", []))
    stats = parse_statistics(full_data.get("statistics", []))
    players = parse_player_performances(full_data.get("players", []))

    print(f"  ✓ 事件数: {len(events)}")
    print(f"  ✓ 统计项: {len(stats)}")
    print(f"  ✓ 球员数: {len(players)}")

    # 展示一些数据样本
    print("\n--- 事件样本（前5条）---")
    for evt in events[:5]:
        print(f"  [{evt['minute']}'] {evt['event_type']}: {evt.get('player_name', '')} - {evt.get('detail', '')}")

    print("\n--- 统计样本（前5条）---")
    for stat in stats[:5]:
        print(f"  {stat['team']} - {stat['stat_type']}: {stat['stat_value']}")

    print("\n--- 球员表现样本（前3条）---")
    for perf in players[:3]:
        print(f"  {perf['player_name']} ({perf['team']}) - 评分:{perf['rating']} 进球:{perf['goals']} 助攻:{perf['assists']}")

    # Step 4: 入库
    print("\nStep 4: 数据入库...")
    init_db()
    db = SessionLocal()
    try:
        match = save_match_to_db(db, target, full_data)
        print(f"  ✓ 比赛已入库: {match.home_team} {match.home_score}-{match.away_score} {match.away_team}")

        # 验证
        db.refresh(match)
        event_count = len(match.events)
        stat_count = len(match.stats)
        perf_count = len(match.performances)
        print(f"  ✓ 入库事件: {event_count} 条")
        print(f"  ✓ 入库统计: {stat_count} 条")
        print(f"  ✓ 入库球员: {perf_count} 条")
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("✅ 数据链路验证通过！")


if __name__ == "__main__":
    asyncio.run(test_pipeline())

"""
批量叙事生成脚本：为所有尚未生成叙事的比赛补充三种风格的叙事。

用法: cd backend && source .venv/bin/activate && python scripts/generate_all_narratives.py
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import SessionLocal, init_db
from app.models.match import Match, Narrative
from app.services.narrative_engine import generate_all_styles
from app.services.rag_context import search_knowledge


def main():
    init_db()
    db = SessionLocal()

    # 查询所有比赛
    matches = db.query(Match).order_by(Match.match_date.desc()).all()
    print(f"数据库中共 {len(matches)} 场比赛\n")

    # 筛选没有叙事的比赛
    pending = []
    for match in matches:
        count = db.query(Narrative).filter(Narrative.match_id == match.id).count()
        status = f"✅ 已有 {count} 条叙事" if count > 0 else "❌ 无叙事"
        print(f"  {match.home_team} {match.home_score}-{match.away_score} {match.away_team} ({match.round}) — {status}")
        if count == 0:
            pending.append(match)

    if not pending:
        print("\n所有比赛都已有叙事数据，无需生成。")
        db.close()
        return

    print(f"\n需要为 {len(pending)} 场比赛生成叙事（每场 3 种风格 × 6 张卡片）")
    print(f"总计 {len(pending) * 3} 次 LLM 调用，预计 5-10 分钟\n")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for i, match in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] {match.home_team} vs {match.away_team} ({match.round})")
        print("-" * 40)

        # RAG 检索
        rag_query = f"{match.home_team} {match.away_team} 世界杯 {match.round}"
        rag_context = search_knowledge(rag_query)
        if rag_context:
            print(f"  RAG: 检索到相关知识")
        else:
            print(f"  RAG: 无相关知识")

        # 生成三种风格
        try:
            result = generate_all_styles(db, match.id, rag_context=rag_context)
            total_cards = sum(len(v) for v in result.values())
            if total_cards > 0:
                success_count += 1
                print(f"  ✅ 生成完成: {total_cards} 张卡片")
            else:
                fail_count += 1
                print(f"  ❌ 生成失败: 无卡片产出")
        except Exception as e:
            fail_count += 1
            print(f"  ❌ 生成异常: {e}")

        # 间隔避免限流
        if i < len(pending):
            print(f"  等待 2 秒...")
            time.sleep(2)

    print(f"\n{'=' * 60}")
    print(f"完成: {success_count} 场成功, {fail_count} 场失败")
    print(f"生成叙事总计: {success_count * 3 * 6} 张卡片")

    db.close()


if __name__ == "__main__":
    main()

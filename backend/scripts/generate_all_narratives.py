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
from app.services.fallback_narrative import is_local_narrative_model
from app.services.narrative_engine import generate_and_save
from app.services.prompts import STYLE_CONFIG
from app.services.rag_context import search_knowledge


def styles_requiring_llm(db, match: Match) -> list[str]:
    """Return styles that are missing or still backed by local fallback text."""
    pending_styles = []
    for style in STYLE_CONFIG:
        narratives = db.query(Narrative).filter(
            Narrative.match_id == match.id,
            Narrative.style == style,
        ).all()
        if not narratives or all(is_local_narrative_model(n.model_version) for n in narratives):
            pending_styles.append(style)
    return pending_styles


def main():
    init_db()
    db = SessionLocal()

    # 查询所有比赛
    matches = db.query(Match).order_by(Match.match_date.desc()).all()
    print(f"数据库中共 {len(matches)} 场比赛\n")

    # 筛选缺失 LLM 叙事的比赛。兜底文案会先占位，但仍需要被 LLM 正式结果替换。
    pending = []
    for match in matches:
        style_status = {}
        pending_styles = styles_requiring_llm(db, match)
        for style in STYLE_CONFIG:
            narratives = db.query(Narrative).filter(
                Narrative.match_id == match.id,
                Narrative.style == style,
            ).all()
            if not narratives:
                style_status[style] = "缺失"
            elif all(is_local_narrative_model(n.model_version) for n in narratives):
                style_status[style] = "兜底"
            else:
                style_status[style] = "LLM"

        status = " / ".join(f"{style}:{value}" for style, value in style_status.items())
        print(f"  {match.home_team} {match.home_score}-{match.away_score} {match.away_team} ({match.round}) — {status}")
        if pending_styles:
            pending.append((match, pending_styles))

    if not pending:
        print("\n所有比赛都已有叙事数据，无需生成。")
        db.close()
        return

    total_calls = sum(len(styles) for _, styles in pending)
    print(f"\n需要为 {len(pending)} 场比赛生成/更新 LLM 叙事")
    print(f"总计 {total_calls} 次 LLM 调用，预计 5-10 分钟\n")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for i, (match, pending_styles) in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] {match.home_team} vs {match.away_team} ({match.round})")
        print(f"待生成风格: {', '.join(pending_styles)}")
        print("-" * 40)

        # RAG 检索
        rag_query = f"{match.home_team} {match.away_team} 世界杯 {match.round}"
        rag_context = search_knowledge(rag_query)
        if rag_context:
            print(f"  RAG: 检索到相关知识")
        else:
            print(f"  RAG: 无相关知识")

        # 仅生成缺失或仍为兜底文案的风格，保留已生成的 LLM 结果。
        try:
            result = {}
            for style in pending_styles:
                config = STYLE_CONFIG[style]
                print(f"  生成 {config['name']}...")
                narratives = generate_and_save(db, match.id, style, rag_context=rag_context)
                result[style] = narratives
                print(f"    ✓ {len(narratives)} 张卡片生成成功")
                time.sleep(1)

            total_cards = sum(len(narratives) for narratives in result.values())
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
    print(f"成功处理比赛数: {success_count}")

    db.close()


if __name__ == "__main__":
    main()

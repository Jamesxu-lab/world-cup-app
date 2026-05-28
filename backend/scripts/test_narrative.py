"""
端到端测试：AI 叙事引擎

用法: cd backend && source .venv/bin/activate && python scripts/test_narrative.py

前提：
1. 已在 .env 中配置 OPENAI_API_KEY
2. 已运行 test_data_pipeline.py 导入测试比赛
3. 已运行 build_knowledge_base.py 构建知识库
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.models.match import Match, Narrative
from app.services.narrative_engine import generate_all_styles
from app.services.quality_check import run_quality_check
from app.services.rag_context import search_knowledge


def test_narrative_generation():
    settings = get_settings()

    if settings.openai_api_key == "your_openai_key_here":
        print("❌ 请先在 backend/.env 中配置 OPENAI_API_KEY")
        return

    init_db()
    db = SessionLocal()

    # 选择测试比赛：优先选决赛（最丰富的数据）
    match = db.query(Match).filter(
        Match.home_team == "Argentina",
        Match.away_team == "France",
    ).first()

    if not match:
        match = db.query(Match).first()

    if not match:
        print("❌ 数据库中没有比赛，请先运行 test_data_pipeline.py")
        db.close()
        return

    print(f"测试比赛: {match.home_team} {match.home_score}-{match.away_score} {match.away_team}")
    print(f"数据: 事件{len(match.events)}条 / 统计{len(match.stats)}项 / 球员{len(match.performances)}人")

    # RAG 检索
    print("\n--- RAG 知识检索测试 ---")
    rag_query = f"{match.home_team} {match.away_team} 世界杯 交锋"
    rag_context = search_knowledge(rag_query)
    if rag_context:
        print(f"检索到相关知识片段")
    else:
        print("未检索到知识（知识库可能未构建，将以无 RAG 模式继续）")

    # 生成三种风格
    print("\n--- 开始生成叙事 ---")
    result = generate_all_styles(db, match.id, rag_context=rag_context)

    # 质量检查
    for style, narratives in result.items():
        if not narratives:
            continue
        cards = [{"card_type": n.card_type, "title": n.title, "content": n.content} for n in narratives]
        quality = run_quality_check(cards, match, style)
        status = "✅ 通过" if quality["passed"] else "⚠️ 有问题"
        print(f"\n[{style}] 质量检查: {status}")
        for issue in quality["issues"]:
            print(f"  - {issue['type']}: {issue['detail']}")

    # 展示生成结果
    for style in ["formal", "funny", "tactical"]:
        narratives = result.get(style, [])
        if not narratives:
            continue
        print(f"\n{'='*60}")
        print(f"【{style}】共 {len(narratives)} 张卡片")
        print(f"{'='*60}")
        for n in narratives:
            print(f"\n--- 卡片 {n.card_index}: {n.card_type} ---")
            print(f"标题: {n.title}")
            print(f"内容: {n.content}")

    db.close()
    print("\n✅ AI 叙事引擎测试完成")


if __name__ == "__main__":
    test_narrative_generation()

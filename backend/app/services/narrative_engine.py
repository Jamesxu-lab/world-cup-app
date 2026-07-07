"""
AI 叙事生成引擎：串联预处理器 → Prompt → LLM → 解析 → 入库。
"""
import json
import re
import time
from sqlalchemy.orm import Session
from openai import OpenAI
from app.core.config import get_settings
from app.models.match import Match, Narrative
from app.services.preprocessor import format_summary_as_text, build_match_summary
from app.services.prompts import STYLE_CONFIG, CARD_COUNT


class NarrativeEngineError(Exception):
    pass


def _get_llm_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=90.0,
        max_retries=1,
    )


def _build_system_prompt(style: str) -> str:
    config = STYLE_CONFIG.get(style)
    if not config:
        raise NarrativeEngineError(f"未知风格: {style}，可选: {list(STYLE_CONFIG.keys())}")
    return config["system"]


def _build_user_prompt(style: str, match_data: str, rag_context: str = "") -> str:
    config = STYLE_CONFIG.get(style)
    if not config:
        raise NarrativeEngineError(f"未知风格: {style}")
    template = config["user"]
    rag_section = f"参考背景知识：\n{rag_context}" if rag_context else ""
    return template.format(match_data=match_data, card_count=CARD_COUNT, rag_context=rag_section)


def _parse_llm_response(raw_text: str) -> list[dict]:
    """从 LLM 返回的文本中解析 JSON 卡片数组"""
    # 尝试直接解析整个响应
    text = raw_text.strip()

    # 移除 markdown 代码块标记
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        cards = json.loads(text)
        if isinstance(cards, list):
            return cards
    except json.JSONDecodeError:
        pass

    # 如果直接解析失败，尝试逐行提取 JSON 对象
    # 查找所有 {...} 对象
    objects = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = -1

    if objects:
        return objects

    raise NarrativeEngineError(f"无法从 LLM 响应中解析 JSON 卡片数组。原始响应:\n{raw_text[:500]}")


def generate_narrative(match: Match, style: str, rag_context: str = "", model: str = None) -> list[dict]:
    """
    为一场比赛生成指定风格的叙事卡片。

    参数：
    - match: Match ORM 对象（需已加载 events/stats/performances）
    - style: "formal" | "funny" | "tactical"
    - rag_context: RAG 检索到的补充知识
    - model: LLM 模型名，不传则使用配置中的默认模型

    返回：
    - 卡片列表 [{card_type, title, content}, ...]
    """
    settings = get_settings()
    model = model or settings.llm_model

    # 构建比赛数据摘要
    match_text = format_summary_as_text(match)

    # 构建 Prompt
    system_prompt = _build_system_prompt(style)
    user_prompt = _build_user_prompt(style, match_text, rag_context)

    # 调用 LLM
    client = _get_llm_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
        max_tokens=4096,
    )

    raw_text = response.choices[0].message.content
    cards = _parse_llm_response(raw_text)
    return cards


def save_narratives(
    db: Session,
    match_id: str,
    style: str,
    cards: list[dict],
    model_version: str = None,
) -> list[Narrative]:
    """将生成的叙事卡片入库，覆盖该场比赛该风格的旧数据。"""
    settings = get_settings()
    model_version = model_version or settings.llm_model

    # 删除该场比赛该风格的旧数据
    db.query(Narrative).filter(
        Narrative.match_id == match_id,
        Narrative.style == style,
    ).delete()

    narratives = []
    for i, card in enumerate(cards):
        narrative = Narrative(
            match_id=match_id,
            style=style,
            card_index=i + 1,
            card_type=card.get("card_type", "unknown"),
            title=card.get("title", ""),
            content=card.get("content", ""),
            model_version=model_version,
        )
        db.add(narrative)
        narratives.append(narrative)

    db.commit()
    return narratives


def generate_and_save(
    db: Session,
    match_id: str,
    style: str,
    rag_context: str = "",
    model: str = None,
) -> list[Narrative]:
    """一站式：生成叙事 + 入库"""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise NarrativeEngineError(f"比赛不存在: {match_id}")

    cards = generate_narrative(match, style, rag_context, model)
    narratives = save_narratives(db, match_id, style, cards, model)
    return narratives


def generate_all_styles(
    db: Session,
    match_id: str,
    rag_context: str = "",
    model: str = None,
) -> dict[str, list[Narrative]]:
    """为一比赛生成全部三种风格的叙事"""
    result = {}
    for style in ["formal", "funny", "tactical"]:
        config = STYLE_CONFIG[style]
        print(f"  生成 {config['name']}...")
        try:
            narratives = generate_and_save(db, match_id, style, rag_context, model)
            result[style] = narratives
            print(f"    ✓ {len(narratives)} 张卡片生成成功")
        except Exception as e:
            print(f"    ✗ 生成失败: {e}")
            result[style] = []
        # 避免请求太快触发限流
        time.sleep(1)
    return result

"""
追问对话引擎：基于比赛数据 + LLM 回答用户问题。
支持同步和 SSE 流式两种响应模式。
优化：持久客户端、轻量上下文(仅关键信息)、selectinload、低 max_tokens。
"""
import json
from functools import lru_cache
from openai import OpenAI
from sqlalchemy.orm import Session, selectinload
from app.core.config import get_settings
from app.models.match import Match, Narrative
from app.services.chat_prompt import CHAT_SYSTEM, CHAT_USER_TEMPLATE
from app.i18n import get_team_cn, get_stadium_cn, get_round_cn

# ── 持久 OpenAI 客户端 ──
_settings = get_settings()
_client: OpenAI = OpenAI(
    api_key=_settings.openai_api_key,
    base_url=_settings.openai_base_url,
)
# 聊天用快速模型（chat_model），未配置时回退到 llm_model
_model: str = _settings.chat_model or _settings.llm_model


@lru_cache(maxsize=32)
def _build_context_cached(match_id: str) -> str:
    """
    构建轻量级聊天上下文：仅包含比分、进球时间线和最佳球员。
    叙事只取 3 张卡片。总 token ~400（优化前 ~2171）。
    """
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        match = db.query(Match).options(
            selectinload(Match.events),
            selectinload(Match.performances),
        ).filter(Match.id == match_id).first()

        if not match:
            return ""

        # 精简摘要（~300 字符 vs 原 2500+ 字符）
        home_cn = get_team_cn(match.home_team)
        away_cn = get_team_cn(match.away_team)
        lines = [
            f"{home_cn} {match.home_score}-{match.away_score} {away_cn}",
            f"{get_round_cn(match.round) if match.round else ''} | {get_stadium_cn(match.stadium) if match.stadium else ''}",
            "",
            "进球:",
        ]
        for evt in sorted(match.events, key=lambda e: (e.minute, e.extra_minute or 0)):
            if evt.event_type == "goal" and evt.minute < 120 and (evt.detail or "") != "Missed Penalty":
                extra = f"+{evt.extra_minute}" if evt.extra_minute else ""
                pen = "(点)" if evt.detail == "Penalty" else ""
                lines.append(f"  [{evt.minute}{extra}'] {evt.player_name}{pen}（{get_team_cn(evt.team)}）")

        lines.append("")
        lines.append("最佳球员:")
        top = sorted(match.performances, key=lambda p: (p.rating or 0, p.goals or 0), reverse=True)[:3]
        for p in top:
            lines.append(f"  {p.player_name}（{get_team_cn(p.team)}）评分{p.rating} {p.goals or 0}球{p.assists or 0}助")

        summary = "\n".join(lines)

        # 叙事只取 3 张 funny 卡片
        narratives = db.query(Narrative.content).filter(
            Narrative.match_id == match.id,
            Narrative.style == "funny",
        ).order_by(Narrative.card_index).limit(3).all()

        if narratives:
            summary += "\n\nAI短评:\n"
            for (content,) in narratives:
                if content:
                    summary += f"- {content}\n"

        return summary
    finally:
        db.close()


def _build_messages(question: str, context: str, history: list[dict] | None) -> list[dict]:
    """构建消息列表"""
    messages = [{"role": "system", "content": CHAT_SYSTEM + context}]

    # 裁剪历史（最多 6 条消息 = 3 轮对话）
    if history:
        messages.extend(history[-6:])

    messages.append({
        "role": "user",
        "content": CHAT_USER_TEMPLATE.format(question=question),
    })
    return messages


def chat(
    db: Session,
    match_id: str,
    question: str,
    history: list[dict] = None,
) -> str:
    """同步模式"""
    context = _build_context_cached(match_id)
    if not context:
        return "抱歉，我没找到这场比赛的数据。"

    messages = _build_messages(question, context, history)
    response = _client.chat.completions.create(
        model=_model,
        messages=messages,
        temperature=0.5,
        max_tokens=100,
    )
    return response.choices[0].message.content.strip()


def chat_stream(
    db: Session,
    match_id: str,
    question: str,
    history: list[dict] = None,
):
    """流式模式：yield SSE token 片段"""
    context = _build_context_cached(match_id)
    if not context:
        yield f"data: {json.dumps({'token': '抱歉，我没找到这场比赛的数据。'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    messages = _build_messages(question, context, history)
    stream = _client.chat.completions.create(
        model=_model,
        messages=messages,
        temperature=0.5,
        max_tokens=100,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield f"data: {json.dumps({'token': delta.content})}\n\n"
    yield "data: [DONE]\n\n"

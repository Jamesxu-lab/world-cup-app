"""
追问对话 API 路由（SSE 流式响应）
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.chat_engine import chat, chat_stream

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    answer: str


@router.post("/matches/{match_id}/chat")
async def chat_about_match(
    match_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """向 AI 追问比赛相关问题 — SSE 流式返回"""
    history = [{"role": m.role, "content": m.content} for m in request.history]

    try:
        return StreamingResponse(
            chat_stream(
                db=db,
                match_id=match_id,
                question=request.question,
                history=history,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 回答失败: {str(e)}")


@router.post("/matches/{match_id}/chat/plain", response_model=ChatResponse)
async def chat_about_match_plain(
    match_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """向 AI 追问比赛相关问题 — 普通 JSON 返回，供微信 H5 回退使用"""
    history = [{"role": m.role, "content": m.content} for m in request.history]

    try:
        answer = chat(
            db=db,
            match_id=match_id,
            question=request.question,
            history=history,
        )
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 回答失败: {str(e)}")

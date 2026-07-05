"""
Chat API 路由
=============
POST /api/v1/chat/stream  —— 流式对话接口（通过 StudyAgent 编排工具）
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import StudyAgent

router = APIRouter()

# ---------- 单例 Agent ----------
study_agent = StudyAgent()


# ---------- 请求体模型 ----------
class ChatRequest(BaseModel):
    message: str
    subject: str | None = None  # 当前会话科目（预留，Agent 内部可按需使用）


# ---------- 流式聊天接口 ----------
@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """
    POST /api/v1/chat/stream
    接收用户消息，通过 StudyAgent 编排工具链，SSE 流式返回最终回复。
    """

    async def event_generator():
        async for chunk in study_agent.run_stream(req.message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
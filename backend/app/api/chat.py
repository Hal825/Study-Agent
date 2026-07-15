"""
Chat API 端点 —— 对话式笔记生成。

- POST /api/chat/stream         → 开始对话，SSE 流式推送
- POST /api/chat/confirm/{id}   → 用户响应后恢复执行
"""

import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.container import get_container

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---- 请求模型 ----

class ChatStartRequest(BaseModel):
    content: str = Field(
        ..., min_length=1, max_length=50000,
        description="用户上传的学习内容（首次消息必需）",
    )
    session_id: str | None = Field(
        default=None,
        description="会话 ID（可选，不提供则自动生成）",
    )


class ChatConfirmRequest(BaseModel):
    message: str = Field(
        default="",
        description="用户的自由文本回复",
    )
    selections: dict | None = Field(
        default=None,
        description="用户的结构化选择，可包含: template, annotations, color_emphasis, format_modifications, topics",
    )


# ---- 端点 ----

@router.post("/stream")
async def chat_stream(request: ChatStartRequest):
    """
    开始一个新的对话式笔记生成会话（SSE 流式推送）。

    流程：
    1. 分析用户上传的内容（parse + extract + analyze）
    2. 展示设计框架（知识主题、格式建议、个性化选项）
    3. 中断，等待用户确认

    Events:
    - chat_progress: 分析进度
    - chat_design_framework: 设计框架数据
    - chat_message: AI 消息
    - chat_option_cards: 选项卡片
    """
    container = get_container()
    executor = container.chat_executor
    session_id = request.session_id or f"chat_{uuid.uuid4().hex[:8]}"

    return StreamingResponse(
        executor.run_stream(
            content=request.content,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/confirm/{session_id}")
async def chat_confirm(session_id: str, request: ChatConfirmRequest):
    """
    用户响应后恢复 Agent 执行（SSE 流式推送）。

    根据当前阶段：
    - design 阶段 → 应用用户偏好 → 流式生成笔记
    - result 阶段 → 处理修订请求或结束对话

    请求体中的 message 为自由文本，selections 为结构化选项。

    Events:
    - chat_progress: 生成进度
    - chat_stream_chunk: 流式笔记块（用于实时预览）
    - chat_note_result: 最终笔记
    - chat_message: AI 消息
    - chat_done: 对话完成
    """
    container = get_container()
    executor = container.chat_executor

    if not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id 不能为空")

    return StreamingResponse(
        executor.resume_stream(
            session_id=session_id,
            user_message=request.message,
            selections=request.selections or {},
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

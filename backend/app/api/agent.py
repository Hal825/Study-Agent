"""
Agent API 端点 —— 智能体笔记生成。

- POST /api/agent/note       → 同步（兼容旧版）
- POST /api/agent/note/stream → SSE 流式（LangGraph 驱动）
"""

import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.container import get_container
from app.prompts.note import VALID_TEMPLATES

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ---- 请求/响应模型 ----
class NoteRequest(BaseModel):
    content: str = Field(
        ..., min_length=1, max_length=50000,
        description="用户上传的学习内容",
    )
    template: str = Field(
        ..., description="笔记模板 ID: outline | summary | cornell | qa",
    )


class NoteResponse(BaseModel):
    result: str = Field(..., description="Markdown 格式的生成笔记")


class ConfirmRequest(BaseModel):
    template: str = Field(
        default="",
        description="用户确认的模板 ID，空字符串表示使用原始模板",
    )


# ---- 同步端点（兼容旧版） ----
@router.post("/note", response_model=NoteResponse)
async def create_note(request: NoteRequest) -> NoteResponse:
    """
    根据上传内容和选定的模板生成学习笔记（同步）。

    内部使用 LangGraph Agent 图执行生成流程。
    """
    if request.template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的模板 ID '{request.template}'，可选值为: {list(VALID_TEMPLATES)}",
        )

    container = get_container()
    executor = container.agent_executor
    session_id = f"sync_note_{uuid.uuid4().hex[:8]}"

    try:
        result = await executor.run_sync(
            content=request.content,
            template_id=request.template,
            session_id=session_id,
        )
        return NoteResponse(result=result)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- SSE 流式端点 ----
@router.post("/note/stream")
async def create_note_stream(request: NoteRequest):
    """
    根据上传内容和选定的模板生成学习笔记（SSE 流式推送）。

    前端连接此端点可实时接收 Agent 执行过程事件：
    - agent_start: Agent 启动
    - stage_change: 阶段变更（parse/extract/analyze/confirm/generate）
    - node_finish: 节点完成
    - agent_finish: 生成完成，data.result 包含笔记
    - agent_error: 出错
    """
    if request.template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的模板 ID '{request.template}'，可选值为: {list(VALID_TEMPLATES)}",
        )

    container = get_container()
    executor = container.agent_executor
    session_id = f"stream_note_{uuid.uuid4().hex[:8]}"

    return StreamingResponse(
        executor.run_stream(
            content=request.content,
            template_id=request.template,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---- 确认端点（Human-in-the-Loop） ----
@router.post("/note/confirm/{session_id}")
async def confirm_note(session_id: str, request: ConfirmRequest):
    """
    确认模板选择并恢复 Agent 执行。

    前端在收到 human_confirm_required 事件后调用此端点，
    传入确认的模板选择，Agent 将继续执行 confirm → generate 节点。

    Returns:
        SSE 流，包含剩余节点的事件
    """
    container = get_container()
    executor = container.agent_executor

    confirmed_template = request.template if request.template else None
    if confirmed_template and confirmed_template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的模板 ID '{confirmed_template}'，可选值为: {list(VALID_TEMPLATES)}",
        )

    return StreamingResponse(
        executor.resume_stream(
            session_id=session_id,
            confirmed_template=confirmed_template,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

"""
Agent API 端点 —— 智能体笔记生成。

- POST /api/agent/note              → 同步（兼容旧版）
- POST /api/agent/note/stream        → SSE 流式（文本输入）
- POST /api/agent/note/vision/stream → SSE 流式（图片输入，Qwen VL 识别）
"""

import uuid
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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


# ---- 视觉识别端点（图片 → 笔记） ----
IMAGE_MAX_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/note/vision/stream")
async def create_note_from_image_stream(
    file: UploadFile = File(..., description="图片文件（jpg/png/webp/gif）"),
    template: str = Form("outline"),
):
    """
    上传图片文件，通过 Qwen VL 识别为 Markdown 文本，
    再进入 Agent 流水线生成笔记（SSE 流式推送）。

    流程：
    1. 校验图片格式和大小
    2. VisionPreprocessorTool 图片 → Markdown
    3. AgentExecutor.run_stream() → SSE 流
    """
    if template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的模板 ID '{template}'，可选值为: {list(VALID_TEMPLATES)}",
        )

    # ---- 1. 校验图片 ----
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    mime = file.content_type or ""
    if not mime.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 '{mime}'，请上传图片文件",
        )

    file_bytes = await file.read()

    if len(file_bytes) > IMAGE_MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"图片文件过大 ({len(file_bytes) / 1024 / 1024:.1f}MB)，上限为 20MB",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # ---- 2. 视觉识别 ----
    container = get_container()
    from app.tools.vision_models import VisionInput

    try:
        vision_result = await container.vision_tool.run(VisionInput(
            image_bytes=file_bytes,
            file_name=file.filename,
        ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片识别失败: {str(e)}")

    if not vision_result.ok:
        raise HTTPException(status_code=500, detail=f"图片识别失败: {vision_result.error}")

    content = vision_result.data.cleaned_markdown

    # ---- 3. Agent 流水线 ----
    executor = container.agent_executor
    session_id = f"vision_note_{uuid.uuid4().hex[:8]}"

    return StreamingResponse(
        executor.run_stream(
            content=content,
            template_id=template,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

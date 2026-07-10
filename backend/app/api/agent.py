"""
Agent API 端点 —— 智能体笔记生成。

Phase 1：将直接 LLM 调用迁移到 Service Layer，
同时新增 SSE 流式端点。
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.container import get_container
from app.prompts.note import NOTE_PROMPTS
from app.services.event_bus import (
    EventType,
    make_event,
    stage_change,
    tool_start,
    tool_finish,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])

VALID_TEMPLATES = set(NOTE_PROMPTS.keys())


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


# ---- 传统请求-响应端点（保留向后兼容） ----
@router.post("/note", response_model=NoteResponse)
async def create_note(request: NoteRequest) -> NoteResponse:
    """
    根据上传内容和选定的模板生成学习笔记（同步）。
    """
    if request.template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的模板 ID '{request.template}'，可选值为: {list(VALID_TEMPLATES)}",
        )

    container = get_container()
    system_prompt = NOTE_PROMPTS[request.template]

    try:
        result = await container.llm_service.generate_legacy(
            system_prompt=system_prompt,
            user_message=request.content,
        )
        return NoteResponse(result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- SSE 流式端点（新增） ----
@router.post("/note/stream")
async def create_note_stream(request: NoteRequest):
    """
    根据上传内容和选定的模板生成学习笔记（SSE 流式推送）。

    前端连接此端点可实时接收 agent 执行过程事件。
    """
    if request.template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的模板 ID '{request.template}'，可选值为: {list(VALID_TEMPLATES)}",
        )

    container = get_container()
    session_id = f"note_{request.template}"

    return StreamingResponse(
        _stream_note_generation(
            content=request.content,
            template_id=request.template,
            session_id=session_id,
            container=container,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_note_generation(
    content: str,
    template_id: str,
    session_id: str,
    container,
):
    """SSE 生成器：逐步推送 agent 执行过程事件。"""
    stages = [
        (0, "读取并理解内容..."),
        (1, "提取关键知识点..."),
        (2, "组织逻辑结构..."),
        (3, "生成笔记内容..."),
    ]
    event_bus = container.event_bus
    system_prompt = NOTE_PROMPTS[template_id]

    try:
        # 1. Agent 开始
        yield _sse(make_event(EventType.AGENT_START, session_id, template=template_id))

        # 2. 模拟阶段推进（Phase 1：真实阶段信息来自后端处理）
        for idx, label in stages[:-1]:
            yield _sse(stage_change(session_id, idx, label))

        # 3. 调用 LLM（作为 generate 阶段）
        yield _sse(stage_change(session_id, 3, stages[-1][1]))
        yield _sse(tool_start(session_id, "llm_generate", {"template": template_id}))

        result = await container.llm_service.generate_legacy(
            system_prompt=system_prompt,
            user_message=content,
        )

        yield _sse(tool_finish(session_id, "llm_generate", 0))

        # 4. Agent 完成
        yield _sse(make_event(
            EventType.AGENT_FINISH, session_id,
            result=result,
        ))

    except Exception as e:
        yield _sse(make_event(
            EventType.AGENT_ERROR, session_id,
            error=str(e),
        ))


def _sse(event) -> str:
    """格式化为 SSE 字符串。"""
    import json
    data = json.dumps(
        {"type": event.type.value, "data": event.data},
        ensure_ascii=False,
    )
    return f"event: {event.type.value}\ndata: {data}\n\n"

"""
Agent API 端点 —— 智能体笔记生成。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.llm.deepseek import generate_note
from app.prompts.note import NOTE_PROMPTS

router = APIRouter(prefix="/api/agent", tags=["agent"])

# 有效的笔记模板 ID
VALID_TEMPLATES = set(NOTE_PROMPTS.keys())


class NoteRequest(BaseModel):
    """笔记生成请求。"""
    content: str = Field(
        ..., min_length=1, max_length=50000,
        description="用户上传的学习内容"
    )
    template: str = Field(
        ..., description="笔记模板 ID: outline | summary | cornell | qa"
    )


class NoteResponse(BaseModel):
    """笔记生成响应。"""
    result: str = Field(..., description="Markdown 格式的生成笔记")


@router.post("/note", response_model=NoteResponse)
async def create_note(request: NoteRequest) -> NoteResponse:
    """
    根据上传内容和选定的模板生成学习笔记。

    - **content**: 待整理的原始学习材料（纯文本/Markdown）
    - **template**: 笔记格式模板
        - `outline` — 大纲笔记（层次结构）
        - `summary` — 详细摘要（段落式）
        - `cornell` — 康奈尔笔记（表格分区）
        - `qa` — 问答笔记（Q&A 格式）

    返回 Markdown 格式的生成笔记供前端渲染。
    """
    if request.template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的模板 ID '{request.template}'，可选值为: {list(VALID_TEMPLATES)}",
        )

    try:
        result = await generate_note(
            content=request.content,
            template_id=request.template,
        )
        return NoteResponse(result=result)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

"""
多格式导出端点 —— DOCX 和 PDF 生成。

业务逻辑已迁移至 services/export_service.py，
此处仅负责 HTTP 层（请求校验、响应构造）。
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.container import get_container
from app.services.export_service import ExportFormat

router = APIRouter(prefix="/api/export", tags=["export"])

EXPORT_FORMATS = ["docx", "pdf"]


class ExportRequest(BaseModel):
    content: str = Field(..., min_length=1)
    format: str = Field(..., description="docx | pdf")


@router.post("")
async def export_document(request: ExportRequest):
    """
    将 Markdown 内容转换为指定格式并返回文件流。
    - format: `docx` (Word) 或 `pdf` (PDF)
    """
    if request.format not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式 '{request.format}'，可选: {EXPORT_FORMATS}",
        )

    container = get_container()
    export_service = container.export_service

    try:
        format_typed: ExportFormat = request.format  # type: ignore[assignment]
        buffer = export_service.export(request.content, format_typed)
        mime_type = export_service.get_mime_type(format_typed)
        filename = export_service.get_filename(format_typed)

        return StreamingResponse(
            buffer,
            media_type=mime_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")

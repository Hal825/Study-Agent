import os
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

router = APIRouter()

# ---------- DeepSeek 客户端 ----------
client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "sk-placeholder"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


# ---------- 请求体模型 ----------
class ChatRequest(BaseModel):
    message: str


# ---------- 流式聊天接口 ----------
@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """
    POST /api/v1/chat/stream
    接收用户消息，通过 SSE 流式返回 DeepSeek Agent 回复。
    """

    async def event_generator():
        try:
            stream = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是 Study Agent，一个拟人化的多科目学习助手。"
                            "你擅长语文、数学、英语三个科目。"
                            "请用友好、耐心的语气回答学生的问题，"
                            "适当使用 emoji 让对话更生动。回答要清晰、有条理。"
                        ),
                    },
                    {"role": "user", "content": req.message},
                ],
                stream=True,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield f"data: {json.dumps({'content': delta.content}, ensure_ascii=False)}\n\n"

            # 发送结束信号
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            error_msg = f"⚠️ AI 服务调用失败：{str(e)}"
            yield f"data: {json.dumps({'content': error_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
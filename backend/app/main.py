"""
Study Agent 后端服务入口。

启动方式:
    uvicorn app.main:app --reload --port 8000
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 加载根目录 .env（backend/../ 即项目根目录）
root_dir = Path(__file__).resolve().parent.parent.parent
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)

# 验证必要环境变量
if not os.getenv("DEEPSEEK_API_KEY"):
    print("⚠️  警告: DEEPSEEK_API_KEY 未设置，API 调用将失败")

app = FastAPI(
    title="Study Agent API",
    description="AI 辅助学习工作流编排后端",
    version="0.1.0",
)

# CORS 中间件 —— 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由
from app.api.agent import router as agent_router  # noqa: E402
from app.api.export import router as export_router  # noqa: E402
app.include_router(agent_router)
app.include_router(export_router)


@app.get("/api/health")
async def health_check():
    """健康检查端点。"""
    return {
        "status": "ok",
        "valid_templates": ["outline", "summary", "cornell", "qa"],
    }

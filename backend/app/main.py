"""
Study Agent 后端服务入口。

启动方式:
    uvicorn app.main:app --reload --port 8000
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.container import get_container

# 加载根目录 .env
root_dir = Path(__file__).resolve().parent.parent.parent
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 —— 启动时初始化服务容器。"""
    # 启动
    container = get_container()
    models = container.llm_service.available_models
    print(f"Study Agent API 启动成功")
    print(f"   可用模型: {models if models else '(无 — 请检查 API Key)'}")
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("   警告: DEEPSEEK_API_KEY 未设置，API 调用将失败")

    # 启动后台清理任务
    await container.cleanup_scheduler.start()
    print(f"   后台清理已启动, 间隔={container.cleanup_scheduler._interval}s")

    yield

    # 关闭
    await container.cleanup_scheduler.stop()
    print("Study Agent API 已关闭")


app = FastAPI(
    title="Study Agent API",
    description="AI 辅助学习 Agent 后端 —— LangGraph 驱动",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
from app.api.agent import router as agent_router  # noqa: E402
from app.api.export import router as export_router  # noqa: E402
app.include_router(agent_router)
app.include_router(export_router)


@app.get("/api/health")
async def health_check():
    """健康检查端点。"""
    container = get_container()
    return {
        "status": "ok",
        "version": "0.2.0",
        "valid_templates": ["outline", "summary", "cornell", "qa"],
        "available_models": container.llm_service.available_models,
    }

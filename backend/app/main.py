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
    """应用生命周期 —— 启动时初始化基础设施 + 服务容器。"""
    # ---- 0. 初始化外部基础设施（仅在 production 模式） ----
    app_env = os.getenv("APP_ENV", "development")

    if app_env == "production":
        database_url = os.getenv("DATABASE_URL")
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        if not database_url:
            raise RuntimeError("APP_ENV=production 时必须设置 DATABASE_URL")

        from app.data.database import init_database, create_tables
        from app.data.redis_client import init_redis

        await init_database(database_url, echo=os.getenv("DB_ECHO", "").lower() == "true")
        await create_tables()
        await init_redis(redis_url)

        host_info = database_url.split("@")[1] if "@" in database_url else database_url
        print(f"   PostgreSQL 已连接: {host_info}")
        print(f"   Redis 已连接: {redis_url}")

    # ---- 1. 启动服务容器 ----
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

    # ---- 关闭 ----
    await container.cleanup_scheduler.stop()

    if app_env == "production":
        from app.data.database import close_database
        from app.data.redis_client import close_redis
        await close_database()
        await close_redis()
        print("   PostgreSQL / Redis 连接已关闭")

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

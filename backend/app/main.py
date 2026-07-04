import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 加载 .env 环境变量
load_dotenv()

# ---------- 数据库连接（先预留，等 Python 3.12 环境稳定后再连） ----------
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://study:admin123@localhost:5432/study_agent")
# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------- 应用生命周期管理 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行（例如：初始化数据库连接池、加载模型等）
    print("🚀 Study-Agent 后端启动中...")
    yield
    # 关闭时执行（例如：释放资源）
    print("🛑 Study-Agent 后端已关闭")

# ---------- 创建 FastAPI 实例 ----------
app = FastAPI(
    title="Study-Agent API",
    description="拟人化多科目学习助手的后端接口",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------- 跨域中间件（允许前端调用） ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite 默认端口
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 注册 API 路由 ----------
from app.api.v1 import router as v1_router

app.include_router(v1_router, prefix="/api")

# ---------- 基础路由 ----------
@app.get("/")
def root():
    return {
        "message": "Study-Agent 后端已就绪！",
        "status": "running",
        "python_version": "3.12",
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# ---------- 其他路由（后续扩展） ----------
# 例如：科目管理、对话、Agent 交互等
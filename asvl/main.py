"""FastAPI应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from configs.settings import get_settings
from configs.logging import log
from asvl.db.session import init_db
from asvl.api.router import task, video, result

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时
    log.info(f"Starting {settings.APP_NAME}...")
    await init_db()
    log.info("Database initialized")

    yield

    # 关闭时
    log.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description="多模态视频理解引擎 - ASR + LLM + VL",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(task.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(video.router, prefix="/api/v1/videos", tags=["videos"])
app.include_router(result.router, prefix="/api/v1/results", tags=["results"])


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "app": settings.APP_NAME}


@app.get("/")
async def root():
    """根路径"""
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
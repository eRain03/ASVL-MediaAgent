"""ASVL 全局配置"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    APP_NAME: str = "ASVL"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/asvl"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM/VL配置 (qwen3-vl-plus)
    LLM_API_KEY: str = "sk-20a0d310c1a0fc3f53f65d5da9b42280"
    LLM_BASE_URL: str = "https://apis.iflow.cn/v1"
    LLM_MODEL: str = "qwen3-vl-plus"

    # 并发限制 (关键: API同时只能1个请求)
    LLM_MAX_CONCURRENT: int = 1
    LLM_REQUEST_TIMEOUT: int = 120
    LLM_RETRY_COUNT: int = 3

    # ASR配置
    ASR_PROVIDER: str = "aliyun"
    ALIYUN_ASR_APP_KEY: Optional[str] = None
    ALIYUN_ASR_ACCESS_KEY: Optional[str] = None
    ALIYUN_ASR_SECRET_KEY: Optional[str] = None
    ALIYUN_ASR_REGION: str = "cn-shanghai"

    # 存储
    STORAGE_TYPE: str = "oss"
    OSS_ENDPOINT: Optional[str] = None
    OSS_ACCESS_KEY_ID: Optional[str] = None
    OSS_ACCESS_KEY_SECRET: Optional[str] = None
    OSS_BUCKET: str = "asvl-videos"

    # 视频处理
    CLIP_PADDING_SECONDS: float = 2.0
    MIN_CLIP_DURATION: float = 5.0
    MAX_CLIP_DURATION: float = 300.0

    # 成本控制
    VL_TOP_K_PERCENT: float = 0.2  # 只处理Top 20%
    MAX_CLIPS_PER_VIDEO: int = 50

    # Worker配置
    CELERY_WORKER_CONCURRENCY: int = 4
    CELERY_TASK_TIME_LIMIT: int = 3600

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """获取配置实例 (缓存)"""
    return Settings()
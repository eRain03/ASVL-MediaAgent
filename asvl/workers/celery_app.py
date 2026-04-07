"""Celery应用配置"""
from celery import Celery
from configs.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "asvl",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "asvl.workers.tasks.asr_task",
        "asvl.workers.tasks.llm_task",
        "asvl.workers.tasks.clip_task",
        "asvl.workers.tasks.vl_task",
        "asvl.workers.tasks.fusion_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_TIME_LIMIT - 300,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
)

# 任务路由 - 按模块分队列，支持独立扩展
celery_app.conf.task_routes = {
    "asvl.workers.tasks.asr_task.*": {"queue": "asr"},
    "asvl.workers.tasks.llm_task.*": {"queue": "llm"},
    "asvl.workers.tasks.clip_task.*": {"queue": "clip"},
    "asvl.workers.tasks.vl_task.*": {"queue": "vl"},
    "asvl.workers.tasks.fusion_task.*": {"queue": "fusion"},
}
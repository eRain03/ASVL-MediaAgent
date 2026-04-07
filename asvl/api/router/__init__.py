"""API路由模块"""
from asvl.api.router.task import router as task_router
from asvl.api.router.video import router as video_router
from asvl.api.router.result import router as result_router

__all__ = ["task_router", "video_router", "result_router"]
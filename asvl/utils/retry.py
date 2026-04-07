"""重试工具"""
import asyncio
from functools import wraps
from typing import Callable, Type, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from configs.logging import log


def async_retry(
    max_attempts: int = 3,
    wait_min: float = 1,
    wait_max: float = 10,
    exceptions: tuple = (Exception,),
):
    """
    异步函数重试装饰器

    Args:
        max_attempts: 最大重试次数
        wait_min: 最小等待时间
        wait_max: 最大等待时间
        exceptions: 要捕获的异常类型

    Returns:
        装饰器函数
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
        retry=retry_if_exception_type(exceptions),
        before_sleep=lambda retry_state: log.warning(
            f"Retrying after {retry_state.outcome.exception()}, attempt {retry_state.attempt_number}"
        ),
    )
"""并发限制器 - 关键：API同时只能1个请求"""
import asyncio
from asyncio import Lock, Semaphore
from typing import Callable, Any, Optional
from collections import deque
from configs.logging import log


class RateLimiter:
    """
    并发限制器

    由于qwen3-vl-plus API限制同时只能发起一个请求，
    需要确保所有请求排队执行。
    """

    def __init__(self, max_concurrent: int = 1):
        """
        初始化限流器

        Args:
            max_concurrent: 最大并发数，默认为1
        """
        self._semaphore = Semaphore(max_concurrent)
        self._lock = Lock()
        self._queue: deque = deque()
        self._request_count = 0
        self._max_concurrent = max_concurrent

        log.info(f"RateLimiter initialized with max_concurrent={max_concurrent}")

    async def acquire(self) -> None:
        """获取执行许可"""
        await self._semaphore.acquire()
        self._request_count += 1
        log.debug(f"Request acquired, current requests: {self._request_count}")

    async def release(self) -> None:
        """释放执行许可"""
        self._semaphore.release()
        self._request_count -= 1
        log.debug(f"Request released, current requests: {self._request_count}")

    async def execute(
        self,
        func: Callable,
        *args,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Any:
        """
        在限流控制下执行异步函数

        Args:
            func: 要执行的异步函数
            *args: 函数参数
            timeout: 超时时间（秒）
            **kwargs: 函数关键字参数

        Returns:
            Any: 函数执行结果

        Raises:
            TimeoutError: 执行超时
        """
        await self.acquire()

        try:
            if timeout:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout,
                )
            else:
                result = await func(*args, **kwargs)
            return result
        except TimeoutError:
            log.error(f"Request timed out after {timeout} seconds")
            raise
        except Exception as e:
            log.error(f"Request failed: {e}")
            raise
        finally:
            await self.release()

    def get_queue_size(self) -> int:
        """获取当前等待队列大小"""
        return len(self._queue)

    def get_active_requests(self) -> int:
        """获取当前活跃请求数"""
        return self._request_count


class RequestQueue:
    """
    请求队列

    用于管理多个LLM请求的排队执行，
    确保请求按顺序处理，避免API限流冲突。
    """

    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
        self._pending_requests: deque = deque()
        self._results: Dict[str, Any] = {}
        self._request_id = 0

    async def enqueue(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> str:
        """
        将请求加入队列

        Returns:
            str: 请求ID
        """
        self._request_id += 1
        request_id = f"req_{self._request_id}"

        self._pending_requests.append({
            "id": request_id,
            "func": func,
            "args": args,
            "kwargs": kwargs,
        })

        log.info(f"Request {request_id} enqueued, queue size: {len(self._pending_requests)}")

        # 启动处理
        asyncio.create_task(self._process_queue())

        return request_id

    async def _process_queue(self) -> None:
        """处理队列中的请求"""
        if not self._pending_requests:
            return

        request = self._pending_requests.popleft()
        request_id = request["id"]

        try:
            result = await self.rate_limiter.execute(
                request["func"],
                *request["args"],
                **request["kwargs"],
            )
            self._results[request_id] = {"status": "completed", "result": result}
            log.info(f"Request {request_id} completed")
        except Exception as e:
            self._results[request_id] = {"status": "failed", "error": str(e)}
            log.error(f"Request {request_id} failed: {e}")

    async def get_result(self, request_id: str, timeout: float = 300) -> Any:
        """
        获取请求结果

        Args:
            request_id: 请求ID
            timeout: 等待超时时间

        Returns:
            Any: 请求结果
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            if request_id in self._results:
                result_data = self._results[request_id]
                if result_data["status"] == "completed":
                    return result_data["result"]
                elif result_data["status"] == "failed":
                    raise Exception(result_data["error"])
            await asyncio.sleep(0.1)

        raise TimeoutError(f"Request {request_id} timed out")
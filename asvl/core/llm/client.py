"""OpenAPI客户端 - qwen3-vl-plus"""
import httpx
import json
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from configs.settings import get_settings
from configs.logging import log
from asvl.core.llm.base import LLMBase
from asvl.core.llm.rate_limiter import RateLimiter

settings = get_settings()


class LLMClient(LLMBase):
    """
    OpenAPI兼容客户端

    使用qwen3-vl-plus模型，支持文本和视觉理解。
    关键：通过RateLimiter控制并发（同时只能1个请求）
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_concurrent: Optional[int] = None,
        timeout: Optional[int] = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = base_url or settings.LLM_BASE_URL
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout or settings.LLM_REQUEST_TIMEOUT
        self.max_concurrent = max_concurrent or settings.LLM_MAX_CONCURRENT

        # 创建限流器（关键！）
        self.rate_limiter = RateLimiter(max_concurrent=self.max_concurrent)

        # HTTP客户端
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(self.timeout),
        )

        log.info(f"LLMClient initialized: model={self.model}, max_concurrent={self.max_concurrent}")

    async def close(self) -> None:
        """关闭客户端"""
        await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _make_request(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        发送请求到API（带重试）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式

        Returns:
            str: 响应内容
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if response_format:
            payload["response_format"] = response_format

        response = await self._client.post(
            "/chat/completions",
            json=payload,
        )

        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"]

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        文本补全

        通过限流器控制并发执行。
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # 关键：通过限流器执行请求
        result = await self.rate_limiter.execute(
            self._make_request,
            messages,
            temperature,
            max_tokens,
            response_format,
            timeout=self.timeout,
        )

        log.debug(f"LLM complete: prompt length={len(prompt)}, result length={len(result)}")
        return result

    async def complete_with_images(
        self,
        prompt: str,
        images: List[str],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        多模态补全（文本+图片）

        Args:
            prompt: 用户提示
            images: 图片URL或base64列表
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            str: 补全结果
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 构建多模态内容
        content = [{"type": "text", "text": prompt}]
        for image in images:
            if image.startswith("http"):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image},
                })
            else:
                # base64图片
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                })

        messages.append({"role": "user", "content": content})

        # 通过限流器执行
        result = await self.rate_limiter.execute(
            self._make_request,
            messages,
            temperature,
            max_tokens,
            None,
            timeout=self.timeout,
        )

        log.debug(f"VL complete: images={len(images)}, result length={len(result)}")
        return result

    async def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """
        JSON格式补全

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数（默认较低以确保稳定输出）

        Returns:
            Dict: JSON解析后的结果
        """
        result = await self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            log.error(f"JSON decode error: {e}, result: {result}")
            raise ValueError(f"Invalid JSON response: {result}")
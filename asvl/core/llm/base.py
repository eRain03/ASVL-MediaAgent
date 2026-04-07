"""LLM抽象基类"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class LLMBase(ABC):
    """LLM模块抽象基类"""

    @abstractmethod
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

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式 (如 {"type": "json_object"})

        Returns:
            str: 补全结果
        """
        pass

    @abstractmethod
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
        pass
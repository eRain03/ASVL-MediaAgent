"""ASR模块"""
from typing import Optional
from asvl.core.asr.base import ASRBase
from asvl.core.asr.aliyun_asr import AliyunASR
from asvl.core.asr.siliconflow_asr import SiliconFlowASR
from asvl.core.asr.audio_extractor import AudioExtractor
from asvl.core.asr.streaming_extractor import StreamingAudioExtractor
from configs.settings import get_settings

__all__ = [
    "ASRBase",
    "AliyunASR",
    "SiliconFlowASR",
    "AudioExtractor",
    "StreamingAudioExtractor",
    "get_asr_provider",
]


def get_asr_provider(provider: Optional[str] = None) -> ASRBase:
    """
    工厂方法：根据配置返回 ASR 实现

    Args:
        provider: ASR提供商名称 (siliconflow / aliyun)
                  如果为None，使用配置中的默认值

    Returns:
        ASRBase: ASR实现实例

    Raises:
        ValueError: 未知的 ASR 提供商
    """
    settings = get_settings()
    provider = provider or settings.ASR_PROVIDER

    if provider == "siliconflow":
        if not settings.SILICONFLOW_ASR_API_KEY:
            raise ValueError("SILICONFLOW_ASR_API_KEY not configured")
        return SiliconFlowASR(
            api_key=settings.SILICONFLOW_ASR_API_KEY,
            model=settings.SILICONFLOW_ASR_MODEL,
            enable_audio_events=settings.ASR_ENABLE_AUDIO_EVENTS,
        )
    elif provider == "aliyun":
        if not all([settings.ALIYUN_ASR_APP_KEY, settings.ALIYUN_ASR_ACCESS_KEY]):
            raise ValueError("Aliyun ASR credentials not configured")
        return AliyunASR(
            app_key=settings.ALIYUN_ASR_APP_KEY,
            access_key=settings.ALIYUN_ASR_ACCESS_KEY,
            secret_key=settings.ALIYUN_ASR_SECRET_KEY,
            region=settings.ALIYUN_ASR_REGION,
        )
    else:
        raise ValueError(f"Unknown ASR provider: {provider}")
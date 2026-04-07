"""ASR模块"""
from asvl.core.asr.base import ASRBase
from asvl.core.asr.aliyun_asr import AliyunASR
from asvl.core.asr.audio_extractor import AudioExtractor

__all__ = ["ASRBase", "AliyunASR", "AudioExtractor"]
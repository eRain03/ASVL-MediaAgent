"""硅基流动 ASR 实现"""
import asyncio
import re
from typing import Optional, List
import aiohttp
from pathlib import Path

from asvl.core.asr.base import ASRBase
from asvl.models.schemas import ASRResult, ASRSegment
from configs.logging import log


class SiliconFlowASR(ASRBase):
    """
    硅基流动 ASR 实现

    API文档: https://docs.siliconflow.cn/cn/api/audio/audio-asr
    特点：
    - 无时间戳返回，需生成伪时间戳
    - 支持 TeleAI/TeleSpeechASR 和 FunAudioLLM/SenseVoiceSmall 模型
    - 文件限制：≤1小时, ≤50MB
    """

    API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"

    def __init__(
        self,
        api_key: str,
        model: str = "TeleAI/TeleSpeechASR",
        chars_per_second: float = 4.0,  # 中文语速估计
    ):
        """
        初始化硅基流动 ASR

        Args:
            api_key: API密钥
            model: 模型名称 (TeleAI/TeleSpeechASR 或 FunAudioLLM/SenseVoiceSmall)
            chars_per_second: 语速估计（字符/秒），用于生成伪时间戳
        """
        self.api_key = api_key
        self.model = model
        self.chars_per_second = chars_per_second
        log.info(f"SiliconFlowASR initialized: model={model}")

    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> ASRResult:
        """
        转录音频文件

        注意：硅基流动 API 不返回时间戳，需要生成伪时间戳

        Args:
            audio_path: 音频文件路径
            language: 语言代码（可选）

        Returns:
            ASRResult: 转录结果，包含分段和置信度
        """
        log.info(f"Transcribing audio: {audio_path}")

        # 1. 调用 API 获取文本
        text = await self._call_api(audio_path)

        if not text:
            log.warning("ASR returned empty text")
            return ASRResult(
                language=language or "zh",
                duration=0.0,
                segments=[],
                confidence=0.0,
            )

        # 2. 获取音频时长
        duration = await self._get_audio_duration(audio_path)

        # 3. 生成伪时间戳分段
        segments = self._generate_pseudo_segments(text, duration)

        # 4. 计算平均置信度
        avg_confidence = sum(s.confidence for s in segments) / len(segments) if segments else 0.0

        log.info(f"Transcription complete: {len(segments)} segments, duration={duration:.2f}s")

        return ASRResult(
            language=language or "zh",
            duration=duration,
            segments=segments,
            confidence=avg_confidence,
        )

    async def extract_audio(
        self,
        video_path: str,
        output_path: str,
    ) -> str:
        """
        从视频中提取音频

        注意：此方法由 AudioExtractor 负责，这里仅为接口兼容

        Args:
            video_path: 视频文件路径
            output_path: 输出音频路径

        Returns:
            str: 输出音频文件路径
        """
        raise NotImplementedError("Use AudioExtractor for audio extraction")

    async def _call_api(self, audio_path: str) -> str:
        """
        调用硅基流动 ASR API

        Args:
            audio_path: 音频文件路径

        Returns:
            str: 转录文本
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # 读取音频文件
        audio_data = Path(audio_path).read_bytes()
        filename = Path(audio_path).name

        # 构建 multipart form
        data = aiohttp.FormData()
        data.add_field(
            "file",
            audio_data,
            filename=filename,
            content_type="audio/wav",
        )
        data.add_field("model", self.model)

        timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时

        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(
                    self.API_URL,
                    headers=headers,
                    data=data,
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        text = result.get("text", "")
                        log.debug(f"ASR response: {text[:100]}...")
                        return text
                    else:
                        error_text = await response.text()
                        log.error(f"ASR API error: {response.status} - {error_text}")
                        raise RuntimeError(f"ASR API error: {response.status} - {error_text}")

            except aiohttp.ClientError as e:
                log.error(f"ASR API request failed: {e}")
                raise RuntimeError(f"ASR API request failed: {e}")

    async def _get_audio_duration(self, audio_path: str) -> float:
        """
        获取音频时长

        Args:
            audio_path: 音频文件路径

        Returns:
            float: 时长（秒）
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            log.warning(f"Failed to get audio duration, using estimate: {stderr.decode()}")
            return 0.0

        return float(stdout.decode().strip())

    def _generate_pseudo_segments(
        self,
        text: str,
        duration: float,
    ) -> List[ASRSegment]:
        """
        生成伪时间戳分段

        基于句子分割和语速估计生成时间戳

        Args:
            text: 转录文本
            duration: 音频时长（秒）

        Returns:
            List[ASRSegment]: 分段列表
        """
        if not text or duration <= 0:
            return []

        # 分割句子
        sentences = self._split_sentences(text)

        if not sentences:
            return []

        segments = []
        current_time = 0.0
        sentence_pause = 0.3  # 句间停顿

        for sent in sentences:
            if not sent.strip():
                continue

            # 估计句子时长
            char_count = len(sent)
            sent_duration = char_count / self.chars_per_second

            # 确保不超过总时长
            end_time = min(current_time + sent_duration, duration)

            # 只添加有效分段
            if end_time > current_time:
                segments.append(ASRSegment(
                    start=current_time,
                    end=end_time,
                    text=sent.strip(),
                    confidence=0.85,  # 默认置信度
                ))

            current_time = end_time + sentence_pause

            # 防止超出总时长
            if current_time >= duration:
                break

        return segments

    def _split_sentences(self, text: str) -> List[str]:
        """
        分割句子

        支持中英文标点

        Args:
            text: 输入文本

        Returns:
            List[str]: 句子列表
        """
        # 中文标点：。！？；：
        # 英文标点：. ! ? ; :
        pattern = r'[。！？；：.!?;:]+'

        # 分割并保留分隔符
        parts = re.split(f'({pattern})', text)

        # 合并句子和标点
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            if i + 1 < len(parts):
                sentence = parts[i] + parts[i + 1]
                if sentence.strip():
                    sentences.append(sentence.strip())
            elif parts[i].strip():
                sentences.append(parts[i].strip())

        # 处理最后剩余的部分
        if len(parts) % 2 == 1 and parts[-1].strip():
            sentences.append(parts[-1].strip())

        return sentences
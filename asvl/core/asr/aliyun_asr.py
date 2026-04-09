"""阿里云ASR客户端"""
import asyncio
import json
import time
import hmac
import hashlib
import base64
import websockets
from datetime import datetime
from typing import Optional, List, Callable, AsyncGenerator
from urllib.parse import urlencode, quote
import uuid

from asvl.core.asr.base import ASRBase
from asvl.models.schemas import ASRResult, ASRSegment
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class AliyunASR(ASRBase):
    """
    阿里云实时语音识别客户端

    支持：
    - 实时语音识别
    - 句级时间戳
    - 多语言识别
    - 长音频处理
    """

    def __init__(
        self,
        app_key: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.app_key = app_key or settings.ALIYUN_ASR_APP_KEY
        self.access_key = access_key or settings.ALIYUN_ASR_ACCESS_KEY
        self.secret_key = secret_key or settings.ALIYUN_ASR_SECRET_KEY
        self.region = region or settings.ALIYUN_ASR_REGION

        if not all([self.app_key, self.access_key, self.secret_key]):
            raise ValueError("Aliyun ASR credentials not configured")

        self.ws_url = f"wss://nls-gateway.{self.region}.aliyuncs.com/ws/v1"
        log.info(f"AliyunASR initialized: region={self.region}")

    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = "zh",
        enable_words: bool = True,
        enable_diarization: bool = False,  # 新增：启用说话人分离
    ) -> ASRResult:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码
            enable_words: 是否启用词级时间戳
            enable_diarization: 是否启用说话人分离（返回 speaker_id）

        Returns:
            ASRResult: 转录结果
        """
        import aiofiles
        import os

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # 获取音频时长
        duration = await self._get_audio_duration(audio_path)

        # 读取音频数据
        async with aiofiles.open(audio_path, "rb") as f:
            audio_data = await f.read()

        # 进行实时识别
        segments = []
        start_time = time.time()

        async for result in self._recognize_stream(
            audio_data=audio_data,
            language=language,
            enable_words=enable_words,
            enable_diarization=enable_diarization,
        ):
            segments.extend(result)

        processing_time = time.time() - start_time

        # 计算平均置信度
        avg_confidence = (
            sum(s.confidence for s in segments) / len(segments)
            if segments else 0.0
        )

        log.info(
            f"ASR completed: {len(segments)} segments, "
            f"duration={duration:.1f}s, time={processing_time:.1f}s, "
            f"diarization={enable_diarization}"
        )

        return ASRResult(
            language=language,
            duration=duration,
            segments=segments,
            confidence=avg_confidence,
        )

    async def _recognize_stream(
        self,
        audio_data: bytes,
        language: str = "zh",
        enable_words: bool = True,
        enable_diarization: bool = False,  # 新增参数
    ) -> AsyncGenerator[List[ASRSegment], None]:
        """
        流式识别

        Args:
            audio_data: 音频数据
            language: 语言
            enable_words: 词级时间戳
            enable_diarization: 说话人分离

        Yields:
            List[ASRSegment]: 识别分段列表
        """
        # 生成Token
        token = await self._get_token()

        # 建立WebSocket连接
        url = f"{self.ws_url}?token={token}"

        async with websockets.connect(url) as ws:
            # 发送开始帧
            await self._send_start_frame(
                ws=ws,
                token=token,
                language=language,
                enable_words=enable_words,
                enable_diarization=enable_diarization,
            )

            # 发送音频数据
            chunk_size = 3200  # 100ms @ 16kHz, 16bit
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i : i + chunk_size]
                await ws.send(chunk)
                await asyncio.sleep(0.01)  # 模拟实时

            # 发送结束帧
            await self._send_end_frame(ws)

            # 接收结果
            segments = []
            async for message in ws:
                result = json.loads(message)

                if result.get("status") == 20000000:
                    # 识别结果
                    for sentence in result.get("payload", {}).get("result", []):
                        segment = self._parse_sentence(sentence)
                        if segment:
                            segments.append(segment)

                if result.get("status") == 20000001:
                    # 流结束
                    break

            yield segments

    async def _send_start_frame(
        self,
        ws,
        token: str,
        language: str,
        enable_words: bool,
        enable_diarization: bool = False,  # 新增参数
    ) -> None:
        """发送开始帧"""
        payload = {
            "format": "pcm",
            "sample_rate": 16000,
            "enable_intermediate_result": True,
            "enable_punctuation_prediction": True,
            "enable_inverse_text_normalization": True,
            "enable_words": enable_words,
            "language": language,
        }

        # 启用说话人分离
        if enable_diarization:
            payload["enable_diarization"] = True
            payload["diarization_speaker_count"] = 2  # 预设说话人数量

        frame = {
            "header": {
                "appkey": self.app_key,
                "message_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "namespace": "SpeechRecognizer",
                "name": "RecognitionStarted",
                "status_text": "SUCCESS",
            },
            "payload": payload,
        }
        await ws.send(json.dumps(frame))

    async def _send_end_frame(self, ws) -> None:
        """发送结束帧"""
        frame = {
            "header": {
                "appkey": self.app_key,
                "message_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "namespace": "SpeechRecognizer",
                "name": "StopRecognition",
            },
            "payload": {},
        }
        await ws.send(json.dumps(frame))

    def _parse_sentence(self, sentence: dict) -> Optional[ASRSegment]:
        """解析识别结果"""
        text = sentence.get("text", "")
        if not text:
            return None

        begin_time = sentence.get("begin_time", 0) / 1000.0  # ms -> s
        end_time = sentence.get("time", 0) / 1000.0

        # 计算置信度
        confidence = sentence.get("confidence", 0.0)
        if confidence:
            confidence = confidence / 100.0  # 0-100 -> 0-1

        # 提取说话人ID（如果启用了说话人分离）
        speaker_id = sentence.get("speaker_id")

        return ASRSegment(
            start=begin_time,
            end=end_time,
            text=text.strip(),
            confidence=confidence,
            speaker_id=speaker_id,  # 新增字段
        )

    async def _get_token(self) -> str:
        """
        获取访问Token

        使用AccessKey生成Token
        """
        # 简化实现：使用AccessKey作为Token
        # 实际生产环境应该调用阿里云Token服务获取临时Token
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        string_to_sign = f"{self.access_key}\n{timestamp}"

        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        token = base64.b64encode(signature).decode("utf-8")
        return token

    async def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        import asyncio

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

        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())

    async def extract_audio(
        self,
        video_path: str,
        output_path: str,
    ) -> str:
        """
        从视频提取音频（使用AudioExtractor）
        """
        from asvl.core.asr.audio_extractor import AudioExtractor

        extractor = AudioExtractor()
        return await extractor.extract(video_path, output_path)
"""ASR处理任务 - 完整实现"""
import asyncio
import os
from pathlib import Path
from celery import shared_task
from datetime import datetime
import httpx

from asvl.workers.celery_app import celery_app
from asvl.core.asr import AliyunASR, AudioExtractor
from asvl.db.session import async_session
from asvl.db.repositories.task_repo import TaskRepository
from asvl.db.models.asr_result import ASRResultModel
from asvl.models.enums import TaskStatus
from asvl.storage.local_storage import LocalStorage
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


@celery_app.task(bind=True, name="asvl.workers.tasks.asr_task.process_asr")
def process_asr(self, task_id: str, video_url: str, options: dict = None):
    """
    ASR处理任务

    Args:
        task_id: 任务ID
        video_url: 视频URL
        options: 处理选项 {language, ...}

    Returns:
        dict: 处理结果
    """
    log.info(f"Starting ASR task for {task_id}")

    # 在同步任务中运行异步代码
    return asyncio.run(_process_asr_async(self, task_id, video_url, options or {}))


async def _process_asr_async(
    task,
    task_id: str,
    video_url: str,
    options: dict,
) -> dict:
    """异步ASR处理"""
    start_time = datetime.now()

    try:
        # 1. 更新任务状态
        await _update_task_status(task_id, TaskStatus.PROCESSING, "asr")

        # 2. 下载视频
        log.info(f"Downloading video: {video_url}")
        video_path = await _download_video(video_url, task_id)

        # 3. 提取音频
        log.info(f"Extracting audio from: {video_path}")
        audio_extractor = AudioExtractor()
        audio_path = await audio_extractor.extract(video_path)

        # 4. 检查视频时长，决定是否分段处理
        video_duration = await audio_extractor._get_duration(video_path)
        segment_duration = 600.0  # 10分钟分段

        if video_duration > segment_duration:
            # 长视频分段处理
            log.info(f"Long video detected ({video_duration}s), segmenting...")
            audio_segments = await audio_extractor.extract_segments(
                video_path, segment_duration=segment_duration
            )
        else:
            # 短视频直接处理
            audio_segments = [{"path": audio_path, "start": 0, "duration": video_duration}]

        # 5. 调用ASR识别
        language = options.get("language", "zh")
        asr = AliyunASR()

        all_segments = []
        for seg_info in audio_segments:
            log.info(f"Processing audio segment: {seg_info['path']}")
            result = await asr.transcribe(
                audio_path=seg_info["path"],
                language=language,
                enable_words=True,
            )

            # 调整时间戳（分段处理时需要偏移）
            for seg in result.segments:
                seg.start += seg_info.get("start", 0)
                seg.end += seg_info.get("start", 0)
                all_segments.append(seg)

        # 6. 存储结果到数据库
        await _save_asr_result(
            task_id=task_id,
            language=language,
            duration=video_duration,
            segments=all_segments,
            processing_time=(datetime.now() - start_time).total_seconds(),
        )

        # 7. 更新任务进度
        await _update_task_progress(task_id, "asr", TaskStatus.COMPLETED)

        # 8. 清理临时文件
        audio_extractor.cleanup(audio_path)
        if os.path.exists(video_path):
            os.remove(video_path)

        log.info(f"ASR task completed for {task_id}")

        return {
            "task_id": task_id,
            "status": "completed",
            "segments_count": len(all_segments),
            "duration": video_duration,
        }

    except Exception as e:
        log.error(f"ASR task failed for {task_id}: {e}")
        await _update_task_status(task_id, TaskStatus.FAILED, "asr", str(e))
        raise


async def _download_video(video_url: str, task_id: str) -> str:
    """下载视频文件"""
    storage = LocalStorage()
    filename = f"{task_id}_video.mp4"
    video_path = storage.get_video_path(filename)

    # 如果本地已存在，直接返回
    if os.path.exists(video_path):
        log.info(f"Video already exists: {video_path}")
        return video_path

    # 下载视频
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.get(video_url, follow_redirects=True)
        response.raise_for_status()

        await storage.save_video(filename, response.content)

    log.info(f"Video downloaded: {video_path}")
    return video_path


async def _save_asr_result(
    task_id: str,
    language: str,
    duration: float,
    segments: list,
    processing_time: float,
) -> None:
    """保存ASR结果到数据库"""
    async with async_session() as session:
        # 计算平均置信度
        avg_confidence = (
            sum(s.confidence for s in segments) / len(segments)
            if segments else 0.0
        )

        # 转换segments为可序列化格式
        segments_data = [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "confidence": s.confidence,
            }
            for s in segments
        ]

        # 创建ASR结果记录
        asr_result = ASRResultModel(
            task_id=task_id,
            language=language,
            duration=duration,
            segments=segments_data,
            confidence=avg_confidence,
            processing_time=processing_time,
        )

        session.add(asr_result)
        await session.commit()

        log.info(f"ASR result saved: {task_id}, {len(segments)} segments")


async def _update_task_status(
    task_id: str,
    status: TaskStatus,
    stage: str = None,
    error_message: str = None,
) -> None:
    """更新任务状态"""
    async with async_session() as session:
        repo = TaskRepository(session)
        await repo.update_status(task_id, status, error_message)


async def _update_task_progress(
    task_id: str,
    stage: str,
    status: TaskStatus,
) -> None:
    """更新任务进度"""
    async with async_session() as session:
        repo = TaskRepository(session)
        await repo.update_progress(task_id, stage, status)


@celery_app.task(name="asvl.workers.tasks.asr_task.get_asr_result")
def get_asr_result(task_id: str) -> dict:
    """
    获取ASR处理结果

    Args:
        task_id: 任务ID

    Returns:
        dict: ASR结果
    """
    return asyncio.run(_get_asr_result_async(task_id))


async def _get_asr_result_async(task_id: str) -> dict:
    """异步获取ASR结果"""
    from sqlalchemy import select
    from asvl.db.models.asr_result import ASRResultModel

    async with async_session() as session:
        result = await session.execute(
            select(ASRResultModel).where(ASRResultModel.task_id == task_id)
        )
        asr_result = result.scalar_one_or_none()

        if not asr_result:
            return {"error": "ASR result not found"}

        return {
            "task_id": task_id,
            "language": asr_result.language,
            "duration": asr_result.duration,
            "segments": asr_result.segments,
            "confidence": asr_result.confidence,
            "processing_time": asr_result.processing_time,
        }
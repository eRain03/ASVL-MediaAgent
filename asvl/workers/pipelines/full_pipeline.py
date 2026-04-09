"""完整处理流水线"""
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from celery import chain, group, chord

from asvl.workers.celery_app import celery_app
from asvl.workers.tasks import (
    process_asr,
    process_llm,
    process_clip,
    process_vl,
    process_fusion,
)
from asvl.db.session import async_session
from asvl.db.repositories.task_repo import TaskRepository
from asvl.models.enums import TaskStatus
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class FullPipeline:
    """
    完整视频处理流水线

    流程：ASR → LLM → Clip → VL → Fusion
    """

    @staticmethod
    def run(task_id: str, video_url: str, options: dict = None):
        """
        运行完整流水线

        使用Celery chain串联所有任务

        Args:
            task_id: 任务ID
            video_url: 视频URL
            options: 处理选项

        Returns:
            str: Celery任务ID
        """
        options = options or {}

        log.info(f"Starting full pipeline for {task_id}")

        # 构建任务链
        # ASR -> LLM -> Clip -> VL -> Fusion
        pipeline_chain = chain(
            # 1. ASR处理
            process_asr.s(task_id, video_url, options),

            # 2. LLM处理（接收ASR结果）
            process_llm.s(task_id),  # 实际调用: process_llm(asr_result, task_id)

            # 3. 视频裁剪（接收LLM结果）
            process_clip.s(task_id, video_url),

            # 4. VL处理（接收Clip结果）
            process_vl.s(task_id),

            # 5. 多模态融合（接收VL结果）
            process_fusion.s(task_id),
        )

        # 异步启动流水线
        result = pipeline_chain.apply_async()

        log.info(f"Pipeline started for {task_id}, chain_id={result.id}")

        return result.id

    @staticmethod
    async def run_async(
        task_id: str,
        video_url: str,
        options: dict = None,
    ) -> Dict[str, Any]:
        """
        异步运行完整流水线（用于测试）

        不使用Celery，直接顺序执行各阶段

        Args:
            task_id: 任务ID
            video_url: 视频URL
            options: 处理选项

        Returns:
            dict: 最终结果
        """
        options = options or {}

        log.info(f"Running async pipeline for {task_id}")
        start_time = datetime.now()

        try:
            # 1. ASR处理
            log.info(f"[{task_id}] Starting ASR...")
            asr_result = await process_asr(task_id, video_url, options)
            log.info(f"[{task_id}] ASR complete: {asr_result.get('segments_count', 0)} segments")

            # 2. LLM处理
            log.info(f"[{task_id}] Starting LLM...")
            llm_result = await process_llm(task_id, asr_result)
            log.info(f"[{task_id}] LLM complete: {llm_result.get('segments_count', 0)} segments")

            # 3. 视频裁剪
            log.info(f"[{task_id}] Starting Clip...")
            clip_result = await process_clip(task_id, llm_result.get("segments", []), video_url)
            log.info(f"[{task_id}] Clip complete: {clip_result.get('clips_count', 0)} clips")

            # 4. VL处理
            log.info(f"[{task_id}] Starting VL...")
            vl_result = await process_vl(task_id, clip_result.get("clips", []))
            log.info(f"[{task_id}] VL complete: {vl_result.get('vl_results_count', 0)} results")

            # 5. 多模态融合
            log.info(f"[{task_id}] Starting Fusion...")
            fusion_result = await process_fusion(task_id, llm_result, vl_result)
            log.info(f"[{task_id}] Fusion complete: {fusion_result.get('highlights_count', 0)} highlights")

            processing_time = (datetime.now() - start_time).total_seconds()

            return {
                "task_id": task_id,
                "status": "completed",
                "processing_time": processing_time,
                "asr": asr_result,
                "llm": llm_result,
                "clip": clip_result,
                "vl": vl_result,
                "fusion": fusion_result,
            }

        except Exception as e:
            log.error(f"Pipeline failed for {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
            }


async def run_pipeline(
    task_id: str,
    video_url: str,
    options: dict = None,
) -> Dict[str, Any]:
    """
    便捷函数：运行完整流水线

    Args:
        task_id: 任务ID
        video_url: 视频URL
        options: 处理选项

    Returns:
        dict: 处理结果
    """
    return await FullPipeline.run_async(task_id, video_url, options)


def trigger_pipeline(task_id: str, video_url: str, options: dict = None) -> str:
    """
    触发异步流水线（Celery）

    Args:
        task_id: 任务ID
        video_url: 视频URL
        options: 处理选项

    Returns:
        str: Celery任务ID
    """
    return FullPipeline.run(task_id, video_url, options)
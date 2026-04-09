"""处理策略选择器"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from configs.settings import get_settings
from configs.logging import log


class ProcessingStrategy(Enum):
    """处理策略枚举"""
    FULL = "full"           # 全量分析（短视频）
    STANDARD = "standard"   # 标准分析（中等视频）
    SAMPLED = "sampled"     # 采样分析（长视频）


@dataclass
class StrategyConfig:
    """策略配置"""
    strategy: ProcessingStrategy
    vl_percent: float = 0.2     # VL 处理比例
    sample_segments: Optional[List[Tuple[float, float]]] = None  # 采样时间段
    description: str = ""


class StrategySelector:
    """
    根据视频时长选择处理策略

    策略：
    - 短视频（≤30秒）：全量分析，100% VL
    - 中等视频（30秒-3分钟）：标准分析，Top 20% VL
    - 长视频（≥3分钟）：采样分析，开头/中间/结尾采样
    """

    def __init__(self):
        settings = get_settings()
        self.thresholds = settings.VIDEO_DURATION_THRESHOLDS
        self.sample_duration = settings.SAMPLE_SEGMENT_DURATION
        self.sample_count = settings.SAMPLE_SEGMENT_COUNT

        log.info(
            f"StrategySelector initialized: thresholds={self.thresholds}, "
            f"sample_duration={self.sample_duration}s"
        )

    def select(self, duration: float) -> StrategyConfig:
        """
        根据视频时长选择处理策略

        Args:
            duration: 视频时长（秒）

        Returns:
            StrategyConfig: 策略配置
        """
        short_threshold = self.thresholds.get("short", 30)
        medium_threshold = self.thresholds.get("medium", 180)

        if duration <= short_threshold:
            # 短视频：全量分析
            return StrategyConfig(
                strategy=ProcessingStrategy.FULL,
                vl_percent=1.0,  # 100% VL
                description=f"短视频（{duration:.1f}s ≤ {short_threshold}s），全量分析",
            )

        elif duration <= medium_threshold:
            # 中等视频：标准分析
            return StrategyConfig(
                strategy=ProcessingStrategy.STANDARD,
                vl_percent=0.2,  # Top 20% VL
                description=f"中等视频（{duration:.1f}s），标准分析，Top 20% VL",
            )

        else:
            # 长视频：采样分析
            sample_segments = self._get_sample_segments(duration)
            return StrategyConfig(
                strategy=ProcessingStrategy.SAMPLED,
                vl_percent=0.3,  # 30% VL（但只处理采样段）
                sample_segments=sample_segments,
                description=f"长视频（{duration:.1f}s > {medium_threshold}s），采样分析",
            )

    def _get_sample_segments(self, duration: float) -> List[Tuple[float, float]]:
        """
        获取采样时间段

        策略：开头 + 中间 + 结尾

        Args:
            duration: 视频总时长

        Returns:
            List[Tuple[float, float]]: 采样时间段列表 [(start, end), ...]
        """
        segments = []
        half_sample = self.sample_duration / 2

        # 开头段
        start_end = min(self.sample_duration, duration)
        segments.append((0.0, start_end))

        if duration > self.sample_duration * 2:
            # 中间段
            mid_start = max(self.sample_duration, duration / 2 - half_sample)
            mid_end = min(duration - self.sample_duration, duration / 2 + half_sample)
            segments.append((mid_start, mid_end))

        if duration > self.sample_duration * 3:
            # 结尾段
            end_start = duration - self.sample_duration
            segments.append((end_start, duration))

        log.debug(f"Sample segments for {duration}s video: {segments}")
        return segments

    def get_vl_limit(self, total_segments: int, strategy: ProcessingStrategy, vl_percent: float) -> int:
        """
        获取 VL 处理数量限制

        Args:
            total_segments: 总分段数
            strategy: 处理策略
            vl_percent: VL 比例

        Returns:
            int: VL 处理数量上限
        """
        if strategy == ProcessingStrategy.FULL:
            return total_segments
        else:
            return max(1, int(total_segments * vl_percent))


# 全局单例
_strategy_selector: Optional[StrategySelector] = None


def get_strategy_selector() -> StrategySelector:
    """获取策略选择器单例"""
    global _strategy_selector
    if _strategy_selector is None:
        _strategy_selector = StrategySelector()
    return _strategy_selector
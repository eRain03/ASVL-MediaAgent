"""时间处理工具"""


def format_timestamp(seconds: float) -> str:
    """
    将秒数转换为时间戳字符串

    Args:
        seconds: 秒数

    Returns:
        str: 时间戳字符串 (HH:MM:SS)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_timestamp(timestamp: str) -> float:
    """
    将时间戳字符串转换为秒数

    Args:
        timestamp: 时间戳字符串 (HH:MM:SS 或 MM:SS)

    Returns:
        float: 秒数
    """
    parts = timestamp.split(":")

    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    else:
        return float(timestamp)


def seconds_to_ms(seconds: float) -> int:
    """秒转毫秒"""
    return int(seconds * 1000)


def ms_to_seconds(ms: int) -> float:
    """毫秒转秒"""
    return ms / 1000.0
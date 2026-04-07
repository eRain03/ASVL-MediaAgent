"""日志配置"""
import sys
from loguru import logger
from configs.settings import get_settings

settings = get_settings()


def setup_logging():
    """配置日志"""

    # 移除默认处理器
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # 添加文件输出
    logger.add(
        "logs/asvl_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",
        retention="7 days",
        compression="zip",
    )

    return logger


# 初始化日志
log = setup_logging()
"""Configs package"""
from configs.settings import get_settings, Settings
from configs.logging import log, setup_logging

__all__ = ["get_settings", "Settings", "log", "setup_logging"]
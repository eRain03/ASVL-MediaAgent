"""存储模块"""
from asvl.storage.oss_client import OSSClient
from asvl.storage.local_storage import LocalStorage

__all__ = ["OSSClient", "LocalStorage"]
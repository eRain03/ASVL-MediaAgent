"""阿里云OSS客户端"""
import oss2
from typing import Optional
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class OSSClient:
    """阿里云OSS客户端"""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ):
        self.endpoint = endpoint or settings.OSS_ENDPOINT
        self.access_key_id = access_key_id or settings.OSS_ACCESS_KEY_ID
        self.access_key_secret = access_key_secret or settings.OSS_ACCESS_KEY_SECRET
        self.bucket_name = bucket_name or settings.OSS_BUCKET

        if not all([self.endpoint, self.access_key_id, self.access_key_secret]):
            log.warning("OSS credentials not configured, using local storage")
            self._enabled = False
            self.bucket = None
        else:
            self._enabled = True
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
            log.info(f"OSSClient initialized: bucket={self.bucket_name}")

    async def upload(
        self,
        object_name: str,
        data: bytes,
    ) -> str:
        """
        上传文件

        Args:
            object_name: 对象名称
            data: 文件数据

        Returns:
            str: 文件URL
        """
        if not self._enabled:
            raise RuntimeError("OSS not configured")

        self.bucket.put_object(object_name, data)
        url = f"https://{self.bucket_name}.{self.endpoint}/{object_name}"
        log.info(f"Uploaded to OSS: {object_name}")
        return url

    async def download(
        self,
        object_name: str,
        local_path: str,
    ) -> str:
        """
        下载文件

        Args:
            object_name: 对象名称
            local_path: 本地路径

        Returns:
            str: 本地文件路径
        """
        if not self._enabled:
            raise RuntimeError("OSS not configured")

        self.bucket.get_object_to_file(object_name, local_path)
        log.info(f"Downloaded from OSS: {object_name} -> {local_path}")
        return local_path

    def get_presigned_url(
        self,
        object_name: str,
        expires: int = 3600,
    ) -> str:
        """
        获取预签名URL

        Args:
            object_name: 对象名称
            expires: 过期时间（秒）

        Returns:
            str: 预签名URL
        """
        if not self._enabled:
            raise RuntimeError("OSS not configured")

        url = self.bucket.sign_url('PUT', object_name, expires)
        return url
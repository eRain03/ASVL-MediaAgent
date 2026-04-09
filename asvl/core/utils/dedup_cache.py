"""去重缓存管理"""
import json
from datetime import datetime
from typing import Optional, Dict, Any
import redis

from configs.settings import get_settings
from configs.logging import log


class DedupCache:
    """
    去重缓存

    使用 Redis 缓存已处理视频的结果
    """

    def __init__(self):
        settings = get_settings()
        self.enabled = settings.DEDUP_ENABLED
        self.ttl = settings.DEDUP_CACHE_TTL
        self.similarity_threshold = settings.DEDUP_SIMILARITY_THRESHOLD

        if self.enabled:
            try:
                self.redis = redis.from_url(settings.REDIS_URL)
                log.info(f"DedupCache initialized: ttl={self.ttl}s, threshold={self.similarity_threshold}")
            except Exception as e:
                log.warning(f"Failed to connect to Redis, dedup disabled: {e}")
                self.enabled = False
        else:
            log.info("DedupCache disabled")

    def _get_cache_key(self, video_hash: str) -> str:
        """获取缓存 key"""
        return f"video_hash:{video_hash}"

    async def get_cached_result(self, video_hash: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的处理结果

        Args:
            video_hash: 视频指纹

        Returns:
            Optional[Dict]: 缓存的结果，无则返回 None
        """
        if not self.enabled:
            return None

        try:
            key = self._get_cache_key(video_hash)
            cached = self.redis.get(key)

            if cached:
                result = json.loads(cached)
                log.info(f"Cache hit for video_hash: {video_hash[:16]}...")
                return result

            log.debug(f"Cache miss for video_hash: {video_hash[:16]}...")
            return None

        except Exception as e:
            log.error(f"Failed to get cached result: {e}")
            return None

    async def set_cached_result(
        self,
        video_hash: str,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        缓存处理结果

        Args:
            video_hash: 视频指纹
            task_id: 任务 ID
            result: 处理结果（可选）

        Returns:
            bool: 是否成功
        """
        if not self.enabled:
            return False

        try:
            key = self._get_cache_key(video_hash)
            cache_data = {
                "task_id": task_id,
                "video_hash": video_hash,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }

            self.redis.setex(key, self.ttl, json.dumps(cache_data))
            log.info(f"Cached result for video_hash: {video_hash[:16]}... (task: {task_id})")
            return True

        except Exception as e:
            log.error(f"Failed to cache result: {e}")
            return False

    async def check_similarity(
        self,
        video_hash: str,
    ) -> Optional[str]:
        """
        检查相似视频

        注意：这个实现较简单，对于大规模数据需要优化

        Args:
            video_hash: 视频指纹

        Returns:
            Optional[str]: 相似视频的 task_id，无则返回 None
        """
        if not self.enabled:
            return None

        try:
            # 扫描所有缓存的视频指纹
            # 注意：生产环境应使用更高效的方式（如 Redis 的有序集合）
            keys = self.redis.keys("video_hash:*")

            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                existing_hash = key_str.replace("video_hash:", "")

                if existing_hash == video_hash:
                    continue

                # 计算汉明距离
                distance = self._hamming_distance(video_hash, existing_hash)

                if distance <= self.similarity_threshold:
                    cached = self.redis.get(key_str)
                    if cached:
                        data = json.loads(cached)
                        log.info(
                            f"Found similar video: distance={distance}, "
                            f"existing_task={data.get('task_id')}"
                        )
                        return data.get("task_id")

            return None

        except Exception as e:
            log.error(f"Failed to check similarity: {e}")
            return None

    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """计算汉明距离"""
        if len(hash1) != len(hash2):
            return max(len(hash1), len(hash2))

        try:
            val1 = int(hash1, 16)
            val2 = int(hash2, 16)
            return bin(val1 ^ val2).count('1')
        except ValueError:
            return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    async def delete_cached_result(self, video_hash: str) -> bool:
        """删除缓存"""
        if not self.enabled:
            return False

        try:
            key = self._get_cache_key(video_hash)
            self.redis.delete(key)
            log.info(f"Deleted cache for video_hash: {video_hash[:16]}...")
            return True
        except Exception as e:
            log.error(f"Failed to delete cache: {e}")
            return False


# 全局单例
_dedup_cache: Optional[DedupCache] = None


def get_dedup_cache() -> DedupCache:
    """获取去重缓存单例"""
    global _dedup_cache
    if _dedup_cache is None:
        _dedup_cache = DedupCache()
    return _dedup_cache
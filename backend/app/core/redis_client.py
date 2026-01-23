"""
Redis 客户端模块
===============

管理 Redis 连接（同步和异步）
"""

import os
import redis
import redis.asyncio as aioredis
from redis import Redis
from typing import Optional


def get_redis_url() -> str:
    """获取 Redis 连接 URL"""
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD", "")
    db = os.getenv("REDIS_DB", "0")
    
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


class RedisClient:
    """Redis 客户端单例（同步）"""

    _instance: Optional[Redis] = None

    @classmethod
    def get_client(cls) -> Redis:
        """获取 Redis 客户端实例"""
        if cls._instance is None:
            password = os.getenv("REDIS_PASSWORD", "")
            cls._instance = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=password if password else None,
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
                socket_connect_timeout=30,  # 增加到 30 秒（远程服务器）
                socket_timeout=30,          # 增加到 30 秒
                socket_keepalive=True,       # 启用 keepalive
                retry_on_timeout=True,       # 超时自动重试
                health_check_interval=30     # health check 间隔
            )
        return cls._instance

    @classmethod
    def close(cls):
        """关闭 Redis 连接"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None


def get_redis() -> Redis:
    """获取同步 Redis 客户端"""
    return RedisClient.get_client()


def get_async_redis() -> aioredis.Redis:
    """获取异步 Redis 客户端（每次调用创建新连接，使用后需关闭）"""
    return aioredis.from_url(
        get_redis_url(), 
        decode_responses=True,
        socket_connect_timeout=30,
        socket_timeout=30
    )

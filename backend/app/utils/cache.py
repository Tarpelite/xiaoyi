from typing import Any, Optional
import json
from app.core.redis_client import get_redis
from app.core.config import settings

REDIS_KEY_PREFIX = settings.REDIS_KEY_PREFIX

def make_redis_key(key_type: str, ticker: str, **kwargs) -> str:
    """生成统一格式的 Redis 键"""
    key_parts = [REDIS_KEY_PREFIX, key_type, ticker]
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")
    return ":".join(key_parts)

def cache_get(key: str) -> Optional[Any]:
    """获取缓存数据（自动解析 JSON）"""
    try:
        redis_client = get_redis()
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"Redis get error: {e}")
    return None

def cache_set(key: str, data: Any, ttl: int = 3600) -> bool:
    """设置缓存数据（自动序列化 JSON）"""
    try:
        redis_client = get_redis()
        redis_client.setex(key, ttl, json.dumps(data, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"Redis set error: {e}")
    return False

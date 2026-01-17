"""
SSE State Manager
=================

管理SSE相关的中间状态存储 (基于Redis)

功能:
- 存储thinking_content增量内容
- 存储chat_response内容
- 管理completion状态
- 支持TTL自动过期
"""

import json
from typing import Optional
from redis import Redis

from app.core.redis_client import get_redis


class SSEStateManager:
    """SSE状态管理器"""
    
    # Redis Key前缀
    THINKING_CONTENT_PREFIX = "message:{message_id}:thinking_content"
    THINKING_COMPLETE_PREFIX = "message:{message_id}:thinking_complete"
    CHAT_RESPONSE_PREFIX = "message:{message_id}:chat_response"
    CHAT_COMPLETE_PREFIX = "message:{message_id}:chat_complete"
    STATE_PREFIX = "message:{message_id}:sse_state"
    
    # TTL: 1小时
    DEFAULT_TTL = 3600
    
    def __init__(self, redis_client: Optional[Redis] = None):
        """
        初始化状态管理器
        
        Args:
            redis_client: Redis客户端，不传则使用默认
        """
        self.redis = redis_client or get_redis()
    
    # ========== Thinking相关 ==========
    
    def append_thinking_chunk(self, message_id: str, chunk: str) -> str:
        """
        追加thinking内容片段
        
        Args:
            message_id: 消息ID
            chunk: 内容片段
            
        Returns:
            累积后的完整thinking内容
        """
        key = self.THINKING_CONTENT_PREFIX.format(message_id=message_id)
        
        # 追加内容
        self.redis.append(key, chunk)
        
        # 设置TTL
        self.redis.expire(key, self.DEFAULT_TTL)
        
        # 返回累积内容
        return self.get_thinking_content(message_id)
    
    def get_thinking_content(self, message_id: str) -> str:
        """
        获取thinking内容
        
        Args:
            message_id: 消息ID
            
        Returns:
            thinking内容，不存在则返回空字符串
        """
        key = self.THINKING_CONTENT_PREFIX.format(message_id=message_id)
        content = self.redis.get(key)
        if not content:
            return ""
        # 兼容不同Redis客户端配置：可能返回str或bytes
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return content
    
    def mark_thinking_complete(self, message_id: str) -> None:
        """
        标记thinking完成
        
        Args:
            message_id: 消息ID
        """
        key = self.THINKING_COMPLETE_PREFIX.format(message_id=message_id)
        self.redis.set(key, "true", ex=self.DEFAULT_TTL)
    
    def is_thinking_complete(self, message_id: str) -> bool:
        """
        检查thinking是否完成
        
        Args:
            message_id: 消息ID
            
        Returns:
            是否完成
        """
        key = self.THINKING_COMPLETE_PREFIX.format(message_id=message_id)
        result = self.redis.get(key)
        if not result:
            return False
        # 兼容str和bytes
        return result == b"true" or result == "true"
    
    # ========== Chat相关 ==========
    
    def append_chat_chunk(self, message_id: str, chunk: str) -> str:
        """
        追加chat响应片段
        
        Args:
            message_id: 消息ID
            chunk: 内容片段
            
        Returns:
            累积后的完整chat响应
        """
        key = self.CHAT_RESPONSE_PREFIX.format(message_id=message_id)
        
        # 追加内容
        self.redis.append(key, chunk)
        
        # 设置TTL
        self.redis.expire(key, self.DEFAULT_TTL)
        
        # 返回累积内容
        return self.get_chat_response(message_id)
    
    def get_full_buffer(self, message_id: str) -> dict:
        """
        获取完整的消息buffer（用于历史回放）
        
        Args:
            message_id: 消息ID
            
        Returns:
            完整的消息状态字典，包含thinking、intent、steps、conclusion等
        """
        import json
        
        buffer_key = f"msg_buffer:{message_id}"
        buffer_data = self.redis.get(buffer_key)
        
        if not buffer_data:
            return {}
        
        if isinstance(buffer_data, bytes):
            buffer_data = buffer_data.decode('utf-8')
        
        try:
            return json.loads(buffer_data)
        except json.JSONDecodeError:
            return {}
    
    def update_buffer(self, message_id: str, updates: dict):
        """
        更新消息buffer（原子操作）
        
        Args:
            message_id: 消息ID
            updates: 要更新的字段字典
        """
        import json
        
        buffer_key = f"msg_buffer:{message_id}"
        
        # 获取现有buffer
        current_buffer = self.get_full_buffer(message_id)
        
        # 合并更新
        current_buffer.update(updates)
        
        # 保存回Redis
        self.redis.setex(
            buffer_key,
            self.DEFAULT_TTL,
            json.dumps(current_buffer, ensure_ascii=False)
        )
    
    def get_chat_response(self, message_id: str) -> str:
        """
        获取chat响应
        
        Args:
            message_id: 消息ID
            
        Returns:
            chat响应内容，不存在则返回空字符串
        """
        key = self.CHAT_RESPONSE_PREFIX.format(message_id=message_id)
        content = self.redis.get(key)
        if not content:
            return ""
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return content
    
    def mark_chat_complete(self, message_id: str) -> None:
        """
        标记chat完成
        
        Args:
            message_id: 消息ID
        """
        key = self.CHAT_COMPLETE_PREFIX.format(message_id=message_id)
        self.redis.set(key, "true", ex=self.DEFAULT_TTL)
    
    def is_chat_complete(self, message_id: str) -> bool:
        """
        检查chat是否完成
        
        Args:
            message_id: 消息ID
            
        Returns:
            是否完成
        """
        key = self.CHAT_COMPLETE_PREFIX.format(message_id=message_id)
        result = self.redis.get(key)
        if not result:
            return False
        return result == b"true" or result == "true"
    
    # ========== 通用状态管理 ==========
    
    def set_state(self, message_id: str, key: str, value: str) -> None:
        """
        设置自定义状态
        
        Args:
            message_id: 消息ID
            key: 状态键
            value: 状态值
        """
        redis_key = self.STATE_PREFIX.format(message_id=message_id)
        self.redis.hset(redis_key, key, value)
        self.redis.expire(redis_key, self.DEFAULT_TTL)
    
    def get_state(self, message_id: str, key: str) -> Optional[str]:
        """
        获取自定义状态
        
        Args:
            message_id: 消息ID
            key: 状态键
            
        Returns:
            状态值，不存在则返回None
        """
        redis_key = self.STATE_PREFIX.format(message_id=message_id)
        value = self.redis.hget(redis_key, key)
        if not value:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value
    
    def get_all_states(self, message_id: str) -> dict:
        """
        获取所有状态
        
        Args:
            message_id: 消息ID
            
        Returns:
            所有状态的字典
        """
        redis_key = self.STATE_PREFIX.format(message_id=message_id)
        states = self.redis.hgetall(redis_key)
        # 兼容str和bytes的key/value
        result = {}
        for k, v in states.items():
            key_str = k.decode("utf-8") if isinstance(k, bytes) else k
            val_str = v.decode("utf-8") if isinstance(v, bytes) else v
            result[key_str] = val_str
        return result
    
    # ========== 清理 ==========
    
    def clear_message_state(self, message_id: str) -> None:
        """
        清理消息的所有SSE状态
        
        Args:
            message_id: 消息ID
        """
        keys = [
            self.THINKING_CONTENT_PREFIX.format(message_id=message_id),
            self.THINKING_COMPLETE_PREFIX.format(message_id=message_id),
            self.CHAT_RESPONSE_PREFIX.format(message_id=message_id),
            self.CHAT_COMPLETE_PREFIX.format(message_id=message_id),
            self.STATE_PREFIX.format(message_id=message_id),
        ]
        self.redis.delete(*keys)

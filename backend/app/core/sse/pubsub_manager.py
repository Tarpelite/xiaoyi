"""
Redis Pub/Sub Manager for SSE Streaming
========================================

管理Redis Pub/Sub通信，实现LLM生成与SSE传输的解耦

核心功能:
- 发布消息到频道
- 订阅频道并异步监听
- 管理频道生命周期
"""

import json
import asyncio
from typing import AsyncIterator, Dict, Any, Optional
from redis.asyncio import Redis
from app.core.redis_client import get_redis


class RedisPubSubManager:
    """Redis Pub/Sub管理器"""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        """
        初始化Pub/Sub管理器
        
        Args:
            redis_client: Redis客户端实例，如果为None则使用默认客户端
        """
        self.redis = redis_client or get_redis()
        self.pubsub = None
    
    async def publish(self, channel: str, message: Dict[str, Any]) -> int:
        """
        发布消息到指定频道
        
        Args:
            channel: 频道名称
            message: 消息内容（将被序列化为JSON）
            
        Returns:
            接收到消息的订阅者数量
        """
        message_json = json.dumps(message, ensure_ascii=False)
        subscribers = self.redis.publish(channel, message_json)
        return subscribers
    
    async def subscribe(self, channel: str) -> AsyncIterator[Dict[str, Any]]:
        """
        订阅频道并异步迭代消息
        
        Args:
            channel: 频道名称
            
        Yields:
            解析后的消息字典
            
        Example:
            async for message in manager.subscribe("channel:msg123"):
                if message['type'] == 'complete':
                    break
                print(message)
        """
        # 创建新的pubsub实例
        self.pubsub = self.redis.pubsub()
        
        try:
            # 订阅频道
            await self.pubsub.subscribe(channel)
            print(f"[PubSub] Subscribed to channel: {channel}")
            
            # 监听消息
            async for redis_message in self.pubsub.listen():
                # 跳过订阅确认消息
                if redis_message['type'] != 'message':
                    continue
                
                # 解析消息
                try:
                    data = redis_message['data']
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    
                    message = json.loads(data)
                    yield message
                    
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"[PubSub] Error decoding message: {e}")
                    continue
                    
        finally:
            # 清理订阅
            await self.close()
    
    async def close(self):
        """关闭Pub/Sub连接"""
        if self.pubsub:
            try:
                await self.pubsub.unsubscribe()
                await self.pubsub.aclose()  # Fixed: use aclose() for async redis
                print("[PubSub] Connection closed")
            except Exception as e:
                print(f"[PubSub] Error closing connection: {e}")
            finally:
                self.pubsub = None


# 频道名称生成辅助函数
def get_message_channel(message_id: str) -> str:
    """获取消息的主频道名称"""
    return f"channel:{message_id}"


def get_thinking_channel(message_id: str) -> str:
    """获取thinking内容的频道名称"""
    return f"channel:thinking:{message_id}"


def get_intent_channel(message_id: str) -> str:
    """获取intent事件的频道名称"""
    return f"channel:intent:{message_id}"


def get_step_channel(message_id: str) -> str:
    """获取step更新的频道名称"""
    return f"channel:step:{message_id}"

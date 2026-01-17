"""
SSE Stream Generator
====================

生成符合SSE标准格式的事件流

SSE格式:
event: <event_type>
data: <json_data>

(空行)
"""

import asyncio
import json
from typing import AsyncGenerator, Optional
from datetime import datetime

from app.schemas.sse_schema import SSEEventBase, HeartbeatEvent


class SSEStreamGenerator:
    """SSE流生成器"""
    
    def __init__(self, heartbeat_interval: int = 15):
        """
        初始化生成器
        
        Args:
            heartbeat_interval: 心跳间隔(秒)，0表示禁用心跳
        """
        self.heartbeat_interval = heartbeat_interval
    
    def format_event(self, event: SSEEventBase) -> str:
        """
        将事件对象格式化为SSE格式
        
        Args:
            event: SSE事件对象
            
        Returns:
            SSE格式的字符串
            
        Example:
            event: thinking_chunk
            data: {"type": "thinking_chunk", "timestamp": "...", ...}
            
            (空行)
        """
        event_dict = event.model_dump()
        event_type = event_dict.get("type", "message")
        
        # SSE格式要求每行以"data: "开头
        # 复杂JSON需要确保正确转义
        data_json = json.dumps(event_dict, ensure_ascii=False)
        
        sse_message = f"event: {event_type}\ndata: {data_json}\n\n"
        return sse_message
    
    async def send_event(self, event: SSEEventBase) -> str:
        """
        发送单个事件 (异步接口)
        
        Args:
            event: SSE事件对象
            
        Returns:
            SSE格式的字符串
        """
        return self.format_event(event)
    
    async def generate_heartbeat(
        self, 
        session_id: str, 
        message_id: str
    ) -> AsyncGenerator[str, None]:
        """
        生成心跳事件流
        
        Args:
            session_id: 会话ID
            message_id: 消息ID
            
        Yields:
            心跳事件的SSE格式字符串
        """
        if self.heartbeat_interval <= 0:
            return
        
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            heartbeat = HeartbeatEvent(
                session_id=session_id,
                message_id=message_id
            )
            yield self.format_event(heartbeat)
    
    async def send_comment(self, comment: str) -> str:
        """
        发送SSE注释 (不会被客户端处理，用于调试)
        
        Args:
            comment: 注释内容
            
        Returns:
            SSE注释格式的字符串
        """
        return f": {comment}\n\n"
    
    async def send_retry(self, milliseconds: int) -> str:
        """
        发送重连间隔指令
        
        Args:
            milliseconds: 重连间隔(毫秒)
            
        Returns:
            SSE retry格式的字符串
        """
        return f"retry: {milliseconds}\n\n"


# ========== 便捷函数 ==========

def create_sse_response(event: SSEEventBase) -> str:
    """
    便捷函数: 快速创建SSE响应
    
    Args:
        event: SSE事件对象
        
    Returns:
        SSE格式的字符串
    """
    generator = SSEStreamGenerator()
    return generator.format_event(event)

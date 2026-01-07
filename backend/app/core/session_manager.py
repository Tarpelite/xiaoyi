"""
会话管理器模块
================

使用内存存储管理对话会话历史
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid


class SessionManager:
    """会话管理器 - 内存存储"""
    
    def __init__(self, max_history: int = 10):
        """
        初始化会话管理器
        
        Args:
            max_history: 每个会话保留的最大对话轮数（默认10轮，即20条消息）
        """
        # 内存存储：session_id -> 对话历史
        self._sessions: Dict[str, List[Dict[str, str]]] = {}
        # 会话最后访问时间
        self._last_access: Dict[str, datetime] = {}
        self.max_history = max_history
    
    def create_session(self) -> str:
        """
        创建新会话
        
        Returns:
            会话ID
        """
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = []
        self._last_access[session_id] = datetime.now()
        return session_id
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        获取会话历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            对话历史列表，格式: [{"role": "user", "content": "..."}, ...]
        """
        if session_id not in self._sessions:
            return []
        
        self._last_access[session_id] = datetime.now()
        return self._sessions[session_id].copy()
    
    def add_message(self, session_id: str, role: str, content: str):
        """
        添加消息到会话历史
        
        Args:
            session_id: 会话ID
            role: 角色 ("user" 或 "assistant")
            content: 消息内容
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        
        self._sessions[session_id].append({
            "role": role,
            "content": content
        })
        
        # 限制历史长度：保留最近 max_history 轮对话（每轮2条消息）
        max_messages = self.max_history * 2
        if len(self._sessions[session_id]) > max_messages:
            self._sessions[session_id] = self._sessions[session_id][-max_messages:]
        
        self._last_access[session_id] = datetime.now()
    
    def clear_session(self, session_id: str):
        """
        清除会话历史
        
        Args:
            session_id: 会话ID
        """
        if session_id in self._sessions:
            self._sessions[session_id] = []
            self._last_access[session_id] = datetime.now()
    
    def delete_session(self, session_id: str):
        """
        删除会话
        
        Args:
            session_id: 会话ID
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._last_access:
            del self._last_access[session_id]
    
    def cleanup_expired(self, hours: int = 24):
        """
        清理过期会话（超过指定小时未访问）
        
        Args:
            hours: 过期时间（小时）
        """
        now = datetime.now()
        expired_sessions = [
            sid for sid, last_time in self._last_access.items()
            if (now - last_time) > timedelta(hours=hours)
        ]
        
        for sid in expired_sessions:
            self.delete_session(sid)
    
    def get_recent_history(self, session_id: str, max_turns: int = 5) -> List[Dict[str, str]]:
        """
        获取最近的对话历史（用于构建上下文）
        
        Args:
            session_id: 会话ID
            max_turns: 最大轮数（默认5轮，即10条消息）
            
        Returns:
            最近的对话历史
        """
        history = self.get_history(session_id)
        max_messages = max_turns * 2
        if len(history) > max_messages:
            return history[-max_messages:]
        return history


# 全局单例
_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """获取会话管理器单例"""
    return _session_manager


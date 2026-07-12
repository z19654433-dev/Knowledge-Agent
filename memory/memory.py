# memory/memory.py
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

class Memory:
    """
    SQLite 长期记忆管理
    负责保存和加载对话历史
    """
    def __init__(self, db_path: str = "memory/chat_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,          -- 'user' 或 'assistant'
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 创建索引，加速按 session_id 查询
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON conversations (session_id)
            """)
            conn.commit()

    def save_message(self, session_id: str, role: str, content: str):
        """保存单条消息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            conn.commit()

    def load_history(self, session_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        加载某个会话的最近 N 条历史记录
        返回格式: [{"role": "user", "content": "你好"}, ...]
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content FROM conversations 
                WHERE session_id = ? 
                ORDER BY id DESC LIMIT ?
                """,
                (session_id, limit)
            )
            rows = cursor.fetchall()
            # 反转顺序，使最早的消息在前（保持上下文顺序）
            history = [{"role": row[0], "content": row[1]} for row in rows[::-1]]
            return history

    def clear_session(self, session_id: str):
        """清空某个会话的所有记忆（慎用）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM conversations WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
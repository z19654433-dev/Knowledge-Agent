import sqlite3
import os
import secrets
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple

class Memory:
    def __init__(self, db_path: str = "memory/chat_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON conversations (session_id)
            """)
            # 用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 认证令牌表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            # 用户会话映射表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_id TEXT NOT NULL UNIQUE,
                    label TEXT DEFAULT 'default',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.commit()

    def save_message(self, session_id: str, role: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            conn.commit()

    def load_history(self, session_id: str, limit: int = 20) -> List[Dict[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content FROM conversations 
                WHERE session_id = ? AND role IN ('user', 'assistant')
                ORDER BY id DESC LIMIT ?
                """,
                (session_id, limit)
            )
            rows = cursor.fetchall()
            return [{"role": row[0], "content": row[1]} for row in rows[::-1]]

    def create_session(self, user_id: int, label: str = "") -> str:
        """创建新会话，返回 session_id"""
        import uuid
        session_id = f"u{user_id}_{uuid.uuid4().hex[:12]}"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO user_sessions (user_id, session_id, label) VALUES (?, ?, ?)",
                (user_id, session_id, label or "新对话"),
            )
            conn.commit()
        return session_id

    def delete_session(self, session_id: str):
        """删除会话及其所有消息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
            conn.commit()

    def clear_session(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM conversations WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()

    # ========== 用户认证 ==========

    @staticmethod
    def _hash_password(password: str) -> str:
        """SHA256 哈希密码"""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def register_user(self, username: str, email: str, password: str) -> Tuple[bool, str]:
        """注册新用户，返回 (成功?, 消息或token)"""
        password_hash = self._hash_password(password)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash),
                )
                user_id = cursor.lastrowid
                # 创建默认 session
                default_session = f"u{user_id}_default"
                cursor.execute(
                    "INSERT INTO user_sessions (user_id, session_id) VALUES (?, ?)",
                    (user_id, default_session),
                )
                # 生成登录 token
                token = secrets.token_hex(32)
                cursor.execute(
                    "INSERT INTO auth_tokens (user_id, token) VALUES (?, ?)",
                    (user_id, token),
                )
                conn.commit()
            return True, token
        except sqlite3.IntegrityError as e:
            msg = str(e)
            if "username" in msg:
                return False, "用户名已存在"
            if "email" in msg:
                return False, "邮箱已被注册"
            return False, "注册失败"

    def login_user(self, username: str, password: str) -> Tuple[bool, str]:
        """用户登录，返回 (成功?, 消息或token)"""
        password_hash = self._hash_password(password)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE (username = ? OR email = ?) AND password_hash = ?",
                (username, username, password_hash),
            )
            row = cursor.fetchone()
            if row is None:
                return False, "用户名/邮箱或密码错误"
            user_id = row[0]
            # 生成 token
            token = secrets.token_hex(32)
            cursor.execute(
                "INSERT INTO auth_tokens (user_id, token) VALUES (?, ?)",
                (user_id, token),
            )
            conn.commit()
        return True, token

    def verify_token(self, token: str) -> Optional[int]:
        """验证 token，返回 user_id 或 None"""
        if not token:
            return None
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id FROM auth_tokens WHERE token = ?",
                (token,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """获取用户信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, display_name, created_at FROM users WHERE id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "display_name": row[3] or row[1],
                "created_at": str(row[4]) if row[4] else "",
            }

    def update_display_name(self, user_id: int, new_name: str) -> bool:
        """更新显示名称"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET display_name = ? WHERE id = ?",
                    (new_name, user_id),
                )
                conn.commit()
                return True
        except Exception:
            return False

    def update_password(self, user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
        """修改密码：验证旧密码 -> 更新新密码"""
        old_hash = self._hash_password(old_password)
        new_hash = self._hash_password(new_password)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE id = ? AND password_hash = ?",
                (user_id, old_hash),
            )
            if cursor.fetchone() is None:
                return False, "旧密码错误"
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user_id),
            )
            conn.commit()
            return True, "密码修改成功"

    def revoke_token(self, token: str):
        """登出：删除 token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
            conn.commit()

    def get_user_default_session(self, user_id: int) -> Optional[str]:
        """获取用户的默认 session_id"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id FROM user_sessions WHERE user_id = ? AND label = 'default'",
                (user_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def get_user_sessions(self, user_id: int) -> List[Dict]:
        """获取用户的所有 session 列表（含预览和消息数）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT s.session_id, s.label, s.created_at, (SELECT content FROM conversations WHERE session_id = s.session_id AND role = 'user' ORDER BY id DESC LIMIT 1) as last_msg, (SELECT COUNT(*) FROM conversations WHERE session_id = s.session_id) as msg_count FROM user_sessions s WHERE s.user_id = ? ORDER BY s.created_at DESC",
                (user_id,),
            )
            return [
                {
                    "session_id": r[0],
                    "label": r[1],
                    "created_at": str(r[2]) if r[2] else "",
                    "preview": (r[3] or "")[:60],
                    "msg_count": r[4] or 0,
                }
                for r in cursor.fetchall()
            ]
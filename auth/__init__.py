"""认证模块：封装用户注册、登录、token 验证"""
from memory.memory import Memory
from typing import Optional, Tuple

_memory = Memory()


def register(username: str, email: str, password: str) -> Tuple[bool, str]:
    """注册新用户，返回 (成功?, token或错误消息)"""
    return _memory.register_user(username, email, password)


def login(username: str, password: str) -> Tuple[bool, str]:
    """用户登录，返回 (成功?, token或错误消息)"""
    return _memory.login_user(username, password)


def logout(token: str):
    """登出：吊销 token"""
    _memory.revoke_token(token)


def verify_token(token: str) -> Optional[int]:
    """验证 token，返回 user_id 或 None"""
    return _memory.verify_token(token)


def get_user_info(user_id: int) -> Optional[dict]:
    """获取用户信息"""
    return _memory.get_user_info(user_id)


def update_display_name(user_id: int, new_name: str) -> bool:
    """更新显示名称"""
    return _memory.update_display_name(user_id, new_name)


def update_password(user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
    """修改密码"""
    return _memory.update_password(user_id, old_password, new_password)


def get_user_sessions_list(user_id: int) -> list:
    """获取用户会话列表"""
    return _memory.get_user_sessions(user_id)


def create_new_session(user_id: int, label: str = "") -> str:
    """创建新会话"""
    return _memory.create_session(user_id, label)


def delete_user_session(user_id: int, session_id: str) -> bool:
    """删除会话（仅当会话属于该用户）。返回是否成功删除"""
    sessions = _memory.get_user_sessions(user_id)
    if not any(s["session_id"] == session_id for s in sessions):
        return False
    _memory.delete_session(session_id)
    return True


def get_default_session(user_id: int) -> Optional[str]:
    """获取用户的默认 session_id"""
    return _memory.get_user_default_session(user_id)


def get_session_history(user_id: int, session_id: str, limit: int = 200) -> Optional[list]:
    """获取指定 session 的历史消息（先验证归属，返回 None 表示无权或不存在）"""
    sessions = _memory.get_user_sessions(user_id)
    if not any(s["session_id"] == session_id for s in sessions):
        return None
    return _memory.load_history(session_id, limit=limit)

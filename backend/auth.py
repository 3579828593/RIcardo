# -*- coding: utf-8 -*-
"""认证模块 — 密码哈希、CSRF、限流（零外部依赖）"""
import hashlib
import secrets
from flask import session, request, jsonify


def hash_password(password: str) -> str:
    """生成密码哈希。格式: pbkdf2_sha256$iterations$salt_hex$hash_hex"""
    salt = secrets.token_hex(16)
    iterations = 300000
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """验证密码。支持可升级格式（通过存储的 iterations）。"""
    try:
        algo, iter_str, salt, hash_hex = stored.split('$')
        iterations = int(iter_str)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def validate_password(password: str):
    """验证密码强度。返回 (ok: bool, msg: str)"""
    if not password or len(password) < 6:
        return False, "密码至少 6 位"
    if len(password) > 128:
        return False, "密码不能超过 128 位"
    return True, ""


def validate_student_id(student_id: str):
    """验证学号格式。返回 (ok: bool, msg: str)"""
    if not student_id or len(student_id) < 3:
        return False, "学号至少 3 个字符"
    if len(student_id) > 32:
        return False, "学号不能超过 32 个字符"
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', student_id):
        return False, "学号只能包含字母、数字、下划线和连字符"
    return True, ""


def ensure_csrf_token() -> str:
    """确保 session 中有 CSRF token，返回 token"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']


def csrf_protect():
    """CSRF 防护中间件。登录用户的非 GET 请求必须带正确的 X-CSRF-Token。
    返回 None 表示通过，返回 (response, status) 表示拒绝。"""
    if request.method == 'GET':
        return None
    if 'user_id' not in session:
        return None  # 未登录用户不受 CSRF 保护
    token = request.headers.get('X-CSRF-Token', '')
    if not secrets.compare_digest(token, session.get('csrf_token', '')):
        return jsonify({"error": "CSRF token invalid"}), 403
    return None


def check_rate_limit(db, key: str, max_count: int, window_minutes: int) -> bool:
    """检查限流。返回 True 表示允许，False 表示超限。"""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    window_start = (now - timedelta(minutes=window_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    with db.connection() as conn:
        conn.execute("DELETE FROM rate_limits WHERE window_start < ?", (window_start,))
        row = conn.execute(
            "SELECT SUM(count) as total FROM rate_limits WHERE key = ? AND window_start >= ?",
            (key, window_start)
        ).fetchone()
        current = row['total'] or 0
        if current >= max_count:
            return False
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            "INSERT INTO rate_limits (key, count, window_start) VALUES (?, 1, ?)",
            (key, now_str)
        )
    return True

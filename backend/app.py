#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask 主程序 - 统一 SQLite 后端"""
import json
import logging
import logging.handlers
import os
import re
import sys
import time
from hmac import compare_digest
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_from_directory, Response

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from config import load_config
from database import QuizDatabase
from lite import render_lite_page
from csv_importer import parse_csv, generate_template, sanitize_question

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
# 避免 Flask/Jinja 解析 Vue 的 {{ }} 插值表达式。
app.jinja_env.variable_start_string = "[["
app.jinja_env.variable_end_string = "]]"
cfg = load_config()
app.secret_key = cfg["security"]["secret_key"]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

from datetime import timedelta
app.config["SESSION_COOKIE_SECURE"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

from auth import (
    hash_password, verify_password, validate_password, validate_student_id,
    ensure_csrf_token, csrf_protect, check_rate_limit
)
from flask import session

db = QuizDatabase(cfg["storage"]["db_path"], cfg["storage"]["backup_dir"])

# 日志
log_cfg = cfg["logging"]
os.makedirs(os.path.dirname(log_cfg["file"]), exist_ok=True)
handler = logging.handlers.RotatingFileHandler(
    log_cfg["file"], maxBytes=log_cfg["max_bytes"], backupCount=log_cfg["backup_count"], encoding="utf-8"
)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
app.logger.setLevel(getattr(logging, log_cfg["level"], logging.INFO))
app.logger.addHandler(handler)
app.logger.addHandler(logging.StreamHandler(sys.stdout))


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not cfg["security"]["admin_enabled"]:
            return jsonify({"error": "管理功能已禁用"}), 403
        token = request.headers.get("X-Admin-Token", "")
        expected = cfg["security"]["admin_token"]
        if not token or not expected or not compare_digest(token, expected):
            return jsonify({"error": "未授权"}), 401
        return f(*args, **kwargs)
    return wrapper


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # CSP: PWA 需要 manifest-src 'self' 加载 manifest.json;
    #      script-src 'self' 允许加载同源 sw-register.js; connect-src 'self' 允许 SW 拉取同源 API/资源
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "manifest-src 'self'; "
        "frame-ancestors 'self'"
    )
    return response


def _positive_int_arg(name: str, default: int, maximum: int = None):
    value = request.args.get(name, default, type=int)
    if value is None or value < 1:
        return None, jsonify({"error": f"{name} 必须为正整数"}), 400
    if maximum is not None:
        value = min(value, maximum)
    return value, None, None


def _get_session_id() -> str:
    """从请求头获取 session_id，用于用户数据隔离。
    前端在 localStorage 生成唯一 ID，每次请求带上 X-Session-Id。
    新用户（无 ID）返回 'anon'，看到的是空数据。"""
    sid = request.headers.get("X-Session-Id", "").strip()
    if not sid or len(sid) < 8:
        return "anon"
    # 限制长度和字符，防止注入
    if len(sid) > 64 or not re.match(r'^[a-zA-Z0-9_-]+$', sid):
        return "anon"
    return sid


def _check_answer(qtype: str, user_answer, correct_answer) -> bool:
    """判分逻辑"""
    if qtype == "multiple":
        if not isinstance(user_answer, list):
            return False
        # 统一转字符串比较，避免混合类型 TypeError
        return sorted(str(x) for x in user_answer) == sorted(str(x) for x in correct_answer)
    if qtype == "true_false":
        ua = str(user_answer).strip()
        ca = str(correct_answer[0]).strip() if correct_answer else ""
        # 支持多种写法
        ua_norm = {"对": True, "正确": True, "true": True, "A": True, "是": True}.get(ua, ua)
        ca_norm = {"对": True, "正确": True, "true": True, "A": True, "是": True}.get(ca, ca)
        if ua_norm is True or ua_norm == "True":
            ua_bool = True
        elif ua_norm is False or ua_norm == "False":
            ua_bool = False
        else:
            ua_bool = str(ua_norm).lower() in ("true", "1", "yes", "对", "正确", "a", "是")
        ca_bool = str(ca_norm).lower() in ("true", "1", "yes", "对", "正确", "a", "是")
        return ua_bool == ca_bool
    if qtype == "fill_blank":
        # 支持多空填空：用户答案和正确答案都是列表
        if isinstance(user_answer, list):
            if not correct_answer:
                return False
            for i, ca in enumerate(correct_answer):
                ua = re.sub(r'\s+', '', str(user_answer[i])) if i < len(user_answer) else ""
                ca_clean = re.sub(r'\s+', '', str(ca))
                if ua != ca_clean:
                    return False
            return True
        # 单空填空
        ua = re.sub(r'\s+', '', str(user_answer))
        ca = re.sub(r'\s+', '', str(correct_answer[0])) if correct_answer else ""
        return ua == ca
    if qtype == "short_answer":
        # 简答先按关键词匹配，后续可接入 AI
        ua = str(user_answer).strip()
        ca = str(correct_answer[0]).strip() if correct_answer else ""
        return ua == ca or ca in ua
    # 单选 / 词汇单选
    ua = str(user_answer).strip().upper() if isinstance(user_answer, str) else str(user_answer).strip()
    ca = str(correct_answer[0]).strip().upper() if correct_answer else ""
    return ua == ca


@app.before_request
def before_request_csrf():
    """CSRF 防护：登录用户的非 GET 请求必须带 X-CSRF-Token。
    /api/auth/ 路由豁免（登录/注册需要建立新 session）。"""
    if request.path.startswith('/api/auth/'):
        return None
    result = csrf_protect()
    if result is not None:
        return result


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/lite")
def lite():
    """轻量版 - 服务端渲染，不依赖 Vue，兼容微信所有内核"""
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    page_size = 1  # 轻量版每页1题，减少 HTML 体积
    result = db.search_questions(page=page, page_size=page_size)
    items = result.get("items", [])
    total = result.get("total", 0)
    total_pages = max(1, (total + page_size - 1) // page_size)
    question = items[0] if items else None

    try:
        stats = db.get_stats()
    except Exception:
        stats = None

    html = render_lite_page(question, page, total_pages, stats)
    resp = Response(html, content_type="text/html; charset=utf-8")
    # 允许浏览器缓存 HTML 5 分钟，二次访问秒开
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@app.route("/sw.js")
def sw_js():
    """以根路径提供 Service Worker,使其作用域 (scope) 覆盖整个站点 (/ 和 /api/)。
    文件物理存放于 static/sw.js,通过此路由以 /sw.js 暴露。"""
    response = send_from_directory(app.static_folder, "sw.js")
    response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    # 允许 SW 注册时使用 scope:'/'
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/api/questions", methods=["GET"])
def api_questions():
    course = request.args.get("course")
    chapter = request.args.get("chapter", type=int)
    qtype = request.args.get("type")
    keyword = request.args.get("keyword")
    knowledge = request.args.get("knowledge")
    bank_id = request.args.get("bank_id", type=int)
    # 权限检查：bank_id 未提供（None）或为 1（官方题库）时不检查
    user = _get_current_user()
    allowed, _, err_resp = _check_bank_access(bank_id, user)
    if not allowed:
        return err_resp
    page, error, status = _positive_int_arg("page", 1)
    if error:
        return error, status
    page_size, error, status = _positive_int_arg("page_size", cfg["quiz"]["default_page_size"], cfg["quiz"]["max_page_size"])
    if error:
        return error, status
    result = db.search_questions(course, chapter, qtype, keyword, knowledge, page, page_size, bank_id=bank_id)
    return jsonify(result)


@app.route("/api/questions/random", methods=["GET"])
def api_random():
    course = request.args.get("course")
    chapter = request.args.get("chapter", type=int)
    qtype = request.args.get("type")
    bank_id = request.args.get("bank_id", type=int)
    # 权限检查
    user = _get_current_user()
    allowed, _, err_resp = _check_bank_access(bank_id, user)
    if not allowed:
        return err_resp
    limit, error, status = _positive_int_arg("limit", 20, 100)
    if error:
        return error, status
    items = db.get_random_questions(course, chapter, qtype, limit, bank_id=bank_id)
    return jsonify({"items": items})


@app.route("/api/chapters", methods=["GET"])
def api_chapters():
    """返回各课程实际包含的章节列表"""
    course = request.args.get("course")
    result = db.get_chapters(course)
    return jsonify(result)


@app.route("/api/questions/<int:qid>", methods=["GET"])
def api_question(qid):
    q = db.get_question(qid)
    if not q:
        return jsonify({"error": "题目不存在"}), 404
    return jsonify(q)


@app.route("/api/submit", methods=["POST"])
def api_submit():
    data = request.get_json(silent=True) or {}
    qid = data.get("question_id")
    user_answer = data.get("answer")
    elapsed = max(0, int(data.get("elapsed_seconds", 0) or 0))
    if not qid:
        return jsonify({"error": "缺少 question_id"}), 400
    # 权限检查：bank_id 可能来自 JSON body，未提供时默认为 1（官方题库）
    user = _get_current_user()
    req_bank_id = data.get("bank_id", 1)
    allowed, _, err_resp = _check_bank_access(req_bank_id, user, write=False)
    if not allowed:
        return err_resp
    q = db.get_question(qid)
    if not q:
        return jsonify({"error": "题目不存在"}), 404
    correct = _check_answer(q["type"], user_answer, q.get("answer", []))
    sid = _get_session_id()
    user_id = user['id'] if user else None
    bank_id = q.get('bank_id', 1) if q else 1
    db.record_answer(qid, user_answer, correct, elapsed, session_id=sid, user_id=user_id, bank_id=bank_id)
    return jsonify({
        "correct": correct,
        "correct_answer": q.get("answer"),
        "explanation": q.get("explanation", ""),
        "knowledge": q.get("knowledge", ""),
    })


@app.route("/api/stats", methods=["GET"])
def api_stats():
    user = _get_current_user()
    user_id = user['id'] if user else None
    return jsonify(db.get_stats(session_id=_get_session_id(), user_id=user_id))


@app.route("/api/mistakes", methods=["GET"])
def api_mistakes():
    page, error, status = _positive_int_arg("page", 1)
    if error:
        return error, status
    page_size, error, status = _positive_int_arg("page_size", 20, cfg["quiz"]["max_page_size"])
    if error:
        return error, status
    user = _get_current_user()
    user_id = user['id'] if user else None
    return jsonify(db.get_mistakes(page, page_size, session_id=_get_session_id(), user_id=user_id))


@app.route("/api/favorites", methods=["GET"])
def api_favorites():
    page, error, status = _positive_int_arg("page", 1)
    if error:
        return error, status
    page_size, error, status = _positive_int_arg("page_size", 20, cfg["quiz"]["max_page_size"])
    if error:
        return error, status
    user = _get_current_user()
    user_id = user['id'] if user else None
    return jsonify(db.get_favorites(page, page_size, session_id=_get_session_id(), user_id=user_id))


@app.route("/api/favorites/<int:qid>", methods=["POST", "DELETE"])
def api_toggle_favorite(qid):
    sid = _get_session_id()
    user = _get_current_user()
    user_id = user['id'] if user else None
    q = db.get_question(qid)
    bank_id = q.get('bank_id', 1) if q else 1
    if request.method == "POST":
        tag = (request.get_json(silent=True) or {}).get("tag")
        added = db.toggle_favorite(qid, tag, session_id=sid, user_id=user_id, bank_id=bank_id)
        return jsonify({"favorited": added})
    else:
        removed = db.remove_favorite(qid, session_id=sid, user_id=user_id)
        return jsonify({"favorited": False, "removed": removed})


@app.route("/api/admin/questions", methods=["GET", "POST"])
@require_admin
def api_admin_questions():
    if request.method == "GET":
        course = request.args.get("course")
        chapter = request.args.get("chapter", type=int)
        qtype = request.args.get("type")
        keyword = request.args.get("keyword")
        page, error, status = _positive_int_arg("page", 1)
        if error:
            return error, status
        page_size, error, status = _positive_int_arg("page_size", 20, 100)
        if error:
            return error, status
        result = db.search_questions(course, chapter, qtype, keyword, None, page, page_size)
        return jsonify(result)
    # POST — 创建单题
    data = request.get_json(silent=True) or {}
    required = {"course", "chapter", "type", "stem", "answer"}
    if not required.issubset(data):
        return jsonify({"error": f"缺少字段: {required - set(data)}"}), 400
    rid = db.add_question(data)
    return jsonify({"id": rid}), 201


@app.route("/api/admin/import/csv", methods=["POST"])
@require_admin
def api_admin_import_csv():
    """CSV 批量导入题目。支持 multipart/form-data (file) 或 JSON (content)。"""
    content = ""
    if "file" in request.files:
        raw = request.files["file"].read()
        # 处理 BOM 和编码
        content = raw.decode("utf-8-sig", errors="replace")
    else:
        data = request.get_json(silent=True) or {}
        content = data.get("content", "")

    if not content or not content.strip():
        return jsonify({"error": "CSV 内容为空"}), 400

    result = parse_csv(content)

    if not result["questions"]:
        error_msg = "CSV 解析失败" if result["errors"] else "没有可导入的题目"
        return jsonify({
            "error": error_msg,
            "parse_errors": result["errors"],
            "parsed_count": 0,
        }), 400

    # 有解析错误但也有有效题目时，仍然导入有效部分
    try:
        import_result = db.batch_add_questions(result["questions"])
        response = {
            "added": import_result["added"],
            "skipped": import_result["skipped"],
            "total": len(result["questions"]),
        }
        if result["errors"]:
            response["parse_errors"] = result["errors"]
        return jsonify(response), 201
    except Exception as e:
        return jsonify({
            "error": f"数据库写入失败: {str(e)}",
            "parsed_count": len(result["questions"]),
            "parse_errors": result["errors"],
        }), 500


@app.route("/api/admin/template", methods=["GET"])
@require_admin
def api_admin_template():
    """下载 CSV 导入模板。"""
    csv_content = generate_template()
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=quiz_template.csv"}
    )


@app.route("/api/admin/questions/<int:qid>", methods=["PUT", "DELETE"])
@require_admin
def api_admin_update(qid):
    if request.method == "DELETE":
        ok = db.delete_question(qid)
        return jsonify({"deleted": ok})
    data = request.get_json(silent=True) or {}
    # 序列化字段
    if "options" in data:
        data["options_json"] = json.dumps(data.pop("options"), ensure_ascii=False)
    if "answer" in data:
        data["answer_json"] = json.dumps(data.pop("answer"), ensure_ascii=False)
    ok = db.update_question(qid, data)
    return jsonify({"updated": ok})


@app.route("/api/admin/dedupe", methods=["POST"])
@require_admin
def api_admin_dedupe():
    removed = db.deduplicate()
    return jsonify({"removed": removed})


@app.route("/api/admin/backup", methods=["POST"])
@require_admin
def api_admin_backup():
    path = db.backup()
    return jsonify({"backup_path": path})


@app.route("/api/reset_stats", methods=["POST"])
def reset_stats():
    """清除当前 session 或 user 的答题记录（统计、错题）"""
    try:
        user = _get_current_user()
        user_id = user['id'] if user else None
        db.reset_progress(session_id=_get_session_id(), user_id=user_id)
        return jsonify({"ok": True, "message": "答题记录已清除"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _get_current_user():
    """获取当前登录用户，未登录返回 None"""
    uid = session.get('user_id')
    if not uid:
        return None
    return db.get_user_by_id(uid)


def _check_bank_access(bank_id, user=None, write=False):
    """检查用户是否有权访问题库。返回 (allowed, bank_data_or_None, error_response_or_None)"""
    if bank_id is None or bank_id == 1:
        return True, None, None  # 官方题库，任何人可读
    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return False, None, (jsonify({"error": "题库不存在"}), 404)
    bank = Bank(bank_data)
    user_obj = User(user) if user else None
    allowed = can_write_bank(user_obj, bank) if write else can_read_bank(user_obj, bank)
    if not allowed:
        return False, bank_data, (jsonify({"error": "无权访问此题库"}), 403)
    return True, bank_data, None


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    student_id = (data.get("student_id") or "").strip()
    password = data.get("password") or ""
    nickname = (data.get("nickname") or "").strip()

    ip = request.remote_addr or "unknown"
    if not check_rate_limit(db, f"register:ip:{ip}", 5, 60):
        return jsonify({"error": "注册过于频繁，请稍后再试"}), 429

    ok, msg = validate_student_id(student_id)
    if not ok:
        return jsonify({"error": msg}), 400
    ok, msg = validate_password(password)
    if not ok:
        return jsonify({"error": msg}), 400
    if not nickname or len(nickname) > 32:
        return jsonify({"error": "昵称不能为空且不超过 32 字符"}), 400

    pw_hash = hash_password(password)
    uid = db.create_user(student_id, pw_hash, nickname)
    if uid is None:
        return jsonify({"error": "学号已注册"}), 409

    session.clear()
    session['user_id'] = uid
    session['role'] = 'student'
    session.permanent = True
    csrf_token = ensure_csrf_token()

    sid = _get_session_id()
    if sid != 'anon':
        db.migrate_session_data(uid, sid)

    return jsonify({
        "id": uid, "student_id": student_id, "nickname": nickname,
        "role": "student", "csrf_token": csrf_token,
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    student_id = (data.get("student_id") or "").strip()
    password = data.get("password") or ""

    ip = request.remote_addr or "unknown"
    if not check_rate_limit(db, f"login:ip:{ip}", 10, 10):
        return jsonify({"error": "登录尝试过于频繁，请 10 分钟后再试"}), 429

    user = db.get_user_by_student_id(student_id)
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({"error": "学号或密码错误"}), 401

    old_csrf = session.get('csrf_token')
    session.clear()
    if old_csrf:
        session['csrf_token'] = old_csrf
    session['user_id'] = user['id']
    session['role'] = user['role']
    session.permanent = True
    csrf_token = ensure_csrf_token()

    sid = _get_session_id()
    if sid != 'anon':
        db.migrate_session_data(user['id'], sid)

    return jsonify({
        "id": user['id'], "student_id": user['student_id'],
        "nickname": user['nickname'], "role": user['role'],
        "csrf_token": csrf_token,
    })


@app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "未登录"}), 401
    return jsonify({
        "id": user["id"],
        "student_id": user["student_id"],
        "nickname": user["nickname"],
        "role": user["role"],
        "csrf_token": session.get("csrf_token", ""),
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


from permissions import can_read_bank, can_write_bank, can_import_to_bank, Bank, User

MAX_BANKS_PER_USER = 20
MAX_IMPORT_PER_DAY = 10
MAX_QUESTIONS_PER_IMPORT = 500
MAX_STEM_LENGTH = 2000
MAX_OPTION_LENGTH = 500


@app.route("/api/banks", methods=["GET", "POST"])
def api_banks():
    user = _get_current_user()
    if request.method == "GET":
        scope = request.args.get("scope", "official")
        if scope == "mine":
            if not user:
                return jsonify({"error": "未登录"}), 401
            banks = db.list_banks(owner_id=user['id'], scope="mine")
        elif scope == "official":
            banks = db.list_banks(scope="official")
        elif scope == "public":
            banks = db.list_banks(scope="public")
        elif scope == "subscribed":
            if not user:
                return jsonify({"error": "未登录"}), 401
            banks = db.list_banks(scope="subscribed", user_id=user['id'])
        else:
            banks = db.list_banks()
        return jsonify({"banks": banks})

    if not user:
        return jsonify({"error": "未登录"}), 401
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    course = (data.get("course") or "").strip()
    description = (data.get("description") or "").strip()
    visibility = data.get("visibility", "private")

    if not name or len(name) > 50:
        return jsonify({"error": "题库名称不能为空且不超过 50 字符"}), 400
    if not course:
        return jsonify({"error": "课程不能为空"}), 400
    if visibility not in ('private', 'public', 'unlisted'):
        return jsonify({"error": "无效的可见性"}), 400

    if db.count_user_banks(user['id']) >= MAX_BANKS_PER_USER:
        return jsonify({"error": f"每人最多创建 {MAX_BANKS_PER_USER} 个题库"}), 400

    bank_id = db.create_bank(owner_id=user['id'], name=name, course=course,
                             description=description, visibility=visibility)
    bank = db.get_bank(bank_id)
    return jsonify(bank), 201


@app.route("/api/banks/<int:bank_id>", methods=["GET", "PUT", "DELETE"])
def api_bank_detail(bank_id):
    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return jsonify({"error": "题库不存在"}), 404

    user = _get_current_user()
    bank = Bank(bank_data)
    user_obj = User(user) if user else None

    if request.method == "GET":
        if not can_read_bank(user_obj, bank):
            return jsonify({"error": "无权访问"}), 403
        return jsonify(bank_data)

    if request.method == "PUT":
        if not can_write_bank(user_obj, bank):
            return jsonify({"error": "无权编辑"}), 403
        data = request.get_json(silent=True) or {}
        db.update_bank(bank_id, data)
        return jsonify(db.get_bank(bank_id))

    if request.method == "DELETE":
        if not can_write_bank(user_obj, bank):
            return jsonify({"error": "无权删除"}), 403
        db.delete_bank(bank_id)
        return jsonify({"ok": True})


@app.route("/api/banks/<int:bank_id>/questions", methods=["GET"])
def api_bank_questions(bank_id):
    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return jsonify({"error": "题库不存在"}), 404
    user = _get_current_user()
    bank = Bank(bank_data)
    user_obj = User(user) if user else None
    if not can_read_bank(user_obj, bank):
        return jsonify({"error": "无权访问"}), 403

    page, error, status = _positive_int_arg("page", 1)
    if error:
        return error, status
    page_size, error, status = _positive_int_arg("page_size", cfg["quiz"]["default_page_size"], cfg["quiz"]["max_page_size"])
    if error:
        return error, status
    result = db.search_questions(page=page, page_size=page_size, bank_id=bank_id)
    return jsonify(result)


@app.route("/api/banks/<int:bank_id>/progress", methods=["GET"])
def api_bank_progress(bank_id):
    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return jsonify({"error": "题库不存在"}), 404
    user = _get_current_user()
    bank = Bank(bank_data)
    user_obj = User(user) if user else None
    if not can_read_bank(user_obj, bank):
        return jsonify({"error": "无权访问"}), 403

    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM questions WHERE bank_id = ?", (bank_id,)).fetchone()[0]
        if user:
            done_ids = [r[0] for r in conn.execute(
                "SELECT DISTINCT question_id FROM answer_records WHERE user_id = ? AND bank_id = ?",
                (user['id'], bank_id)
            ).fetchall()]
            correct = conn.execute(
                "SELECT COUNT(*) FROM answer_records WHERE correct = 1 AND user_id = ? AND bank_id = ?",
                (user['id'], bank_id)
            ).fetchone()[0]
            total_answers = conn.execute(
                "SELECT COUNT(*) FROM answer_records WHERE user_id = ? AND bank_id = ?",
                (user['id'], bank_id)
            ).fetchone()[0]
        else:
            sid = _get_session_id()
            done_ids = [r[0] for r in conn.execute(
                "SELECT DISTINCT question_id FROM answer_records WHERE session_id = ? AND bank_id = ?",
                (sid, bank_id)
            ).fetchall()]
            correct = conn.execute(
                "SELECT COUNT(*) FROM answer_records WHERE correct = 1 AND session_id = ? AND bank_id = ?",
                (sid, bank_id)
            ).fetchone()[0]
            total_answers = conn.execute(
                "SELECT COUNT(*) FROM answer_records WHERE session_id = ? AND bank_id = ?",
                (sid, bank_id)
            ).fetchone()[0]

    return jsonify({
        "done_question_ids": done_ids,
        "total": total,
        "done": len(done_ids),
        "correct_rate": round(correct / total_answers, 4) if total_answers else 0,
    })


@app.route("/api/banks/<int:bank_id>/import", methods=["POST"])
def api_bank_import(bank_id):
    """CSV 导入到指定题库"""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "未登录"}), 401

    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return jsonify({"error": "题库不存在"}), 404

    bank = Bank(bank_data)
    user_obj = User(user)
    if not can_import_to_bank(user_obj, bank):
        return jsonify({"error": "无权导入到此题库"}), 403

    # 限流
    if not check_rate_limit(db, f"import:user:{user['id']}", MAX_IMPORT_PER_DAY, 1440):
        return jsonify({"error": f"今天导入次数已达上限 ({MAX_IMPORT_PER_DAY} 次)"}), 429

    # 读取 CSV 内容
    content = ""
    if "file" in request.files:
        raw = request.files["file"].read()
        content = raw.decode("utf-8-sig", errors="replace")
    else:
        data = request.get_json(silent=True) or {}
        content = data.get("content", "")

    if not content or not content.strip():
        return jsonify({"error": "CSV 内容为空"}), 400

    result = parse_csv(content)
    if not result["questions"]:
        return jsonify({
            "ok": False,
            "error": "没有可导入的题目",
            "parse_errors": result["errors"],
        }), 400

    if len(result["questions"]) > MAX_QUESTIONS_PER_IMPORT:
        return jsonify({
            "ok": False,
            "error": f"单次导入不能超过 {MAX_QUESTIONS_PER_IMPORT} 题",
        }), 400

    # sanitize 每道题
    flagged_count = 0
    valid_questions = []
    errors = list(result["errors"])
    for i, q in enumerate(result["questions"]):
        sq = sanitize_question(q)
        if sq.get('_error'):
            errors.append({"row": i + 2, "reason": sq['_error']})
            continue
        if sq.get('_flagged'):
            flagged_count += 1
        valid_questions.append(sq)

    if not valid_questions:
        return jsonify({
            "ok": False,
            "error": "所有题目都被过滤",
            "parse_errors": errors,
        }), 400

    # 写入数据库
    try:
        import_result = db.batch_add_questions(valid_questions, bank_id=bank_id)
        db.update_bank_question_count(bank_id)
        return jsonify({
            "ok": True,
            "imported": import_result["added"],
            "skipped": import_result["skipped"],
            "flagged": flagged_count,
            "errors": errors,
        }), 201
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"数据库写入失败: {str(e)}",
            "parse_errors": errors,
        }), 500


@app.route("/api/questions/<int:qid>/report", methods=["POST"])
def api_report_question(qid):
    """举报题目（登录或匿名）"""
    q = db.get_question(qid)
    if not q:
        return jsonify({"error": "题目不存在"}), 404

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    detail = (data.get("detail") or "").strip()
    if not reason:
        return jsonify({"error": "举报原因不能为空"}), 400

    user = _get_current_user()
    reporter_id = user['id'] if user else None
    session_id = _get_session_id() if not user else None

    # 限流
    ip = request.remote_addr or "unknown"
    rate_key = f"report:ip:{ip}" if not user else f"report:user:{user['id']}"
    if not check_rate_limit(db, rate_key, 5, 60):
        return jsonify({"error": "举报过于频繁，请稍后再试"}), 429

    report_id = db.create_report(qid, reason, detail, reporter_id, session_id)
    if report_id is None:
        return jsonify({"error": "你已经举报过这道题"}), 409

    return jsonify({"id": report_id, "ok": True}), 201


@app.route("/api/admin/reports", methods=["GET"])
@require_admin
def api_admin_reports():
    """管理员查看举报列表"""
    status = request.args.get("status")
    reports = db.list_reports(status)
    return jsonify({"reports": reports})


@app.route("/api/admin/reports/<int:report_id>", methods=["PUT"])
@require_admin
def api_admin_handle_report(report_id):
    """管理员处理举报"""
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    admin_note = data.get("admin_note", "")
    if status not in ('resolved', 'dismissed'):
        return jsonify({"error": "无效状态"}), 400
    ok = db.handle_report(report_id, status, admin_note)
    if not ok:
        return jsonify({"error": "举报不存在"}), 404
    return jsonify({"ok": True, "status": status})


@app.route("/api/banks/<int:bank_id>/subscribe", methods=["POST", "DELETE"])
def api_bank_subscribe(bank_id):
    """订阅/退订公开题库"""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "未登录"}), 401

    bank_data = db.get_bank(bank_id)
    if not bank_data:
        return jsonify({"error": "题库不存在"}), 404

    bank = Bank(bank_data)

    if request.method == "POST":
        # 只能订阅公开且活跃的题库
        if bank.visibility != 'public' or bank.status not in ('active',):
            return jsonify({"error": "只能订阅公开题库"}), 403
        db.subscribe_bank(user['id'], bank_id)
        return jsonify({"ok": True})
    else:
        db.unsubscribe_bank(user['id'], bank_id)
        return jsonify({"ok": True})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    app.logger.exception("Server error")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # 本地开发：未设置 admin token 时使用开发默认值并警告
    if cfg["security"]["admin_enabled"] and not cfg["security"].get("admin_token"):
        os.environ["QUIZ_ADMIN_TOKEN"] = "local-dev-only"
        cfg["security"]["admin_token"] = "local-dev-only"
        app.logger.warning("⚠ 未设置 QUIZ_ADMIN_TOKEN，使用本地开发默认值。生产环境必须设置环境变量！")
    app.run(host=cfg["server"]["host"], port=cfg["server"]["port"], debug=cfg["server"]["debug"])

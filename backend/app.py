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
from csv_importer import parse_csv, generate_template

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
# 避免 Flask/Jinja 解析 Vue 的 {{ }} 插值表达式。
app.jinja_env.variable_start_string = "[["
app.jinja_env.variable_end_string = "]]"
cfg = load_config()
app.secret_key = cfg["security"]["secret_key"]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

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
        return sorted(user_answer) == sorted(correct_answer)
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
    page, error, status = _positive_int_arg("page", 1)
    if error:
        return error, status
    page_size, error, status = _positive_int_arg("page_size", cfg["quiz"]["default_page_size"], cfg["quiz"]["max_page_size"])
    if error:
        return error, status
    result = db.search_questions(course, chapter, qtype, keyword, knowledge, page, page_size)
    return jsonify(result)


@app.route("/api/questions/random", methods=["GET"])
def api_random():
    course = request.args.get("course")
    chapter = request.args.get("chapter", type=int)
    qtype = request.args.get("type")
    limit, error, status = _positive_int_arg("limit", 20, 100)
    if error:
        return error, status
    items = db.get_random_questions(course, chapter, qtype, limit)
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
    elapsed = data.get("elapsed_seconds", 0)
    if not qid:
        return jsonify({"error": "缺少 question_id"}), 400
    q = db.get_question(qid)
    if not q:
        return jsonify({"error": "题目不存在"}), 404
    correct = _check_answer(q["type"], user_answer, q.get("answer", []))
    sid = _get_session_id()
    db.record_answer(qid, user_answer, correct, elapsed, session_id=sid)
    return jsonify({
        "correct": correct,
        "correct_answer": q.get("answer"),
        "explanation": q.get("explanation", ""),
        "knowledge": q.get("knowledge", ""),
    })


@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(db.get_stats(session_id=_get_session_id()))


@app.route("/api/mistakes", methods=["GET"])
def api_mistakes():
    page, error, status = _positive_int_arg("page", 1)
    if error:
        return error, status
    page_size, error, status = _positive_int_arg("page_size", 20, cfg["quiz"]["max_page_size"])
    if error:
        return error, status
    return jsonify(db.get_mistakes(page, page_size, session_id=_get_session_id()))


@app.route("/api/favorites", methods=["GET"])
def api_favorites():
    page, error, status = _positive_int_arg("page", 1)
    if error:
        return error, status
    page_size, error, status = _positive_int_arg("page_size", 20, cfg["quiz"]["max_page_size"])
    if error:
        return error, status
    return jsonify(db.get_favorites(page, page_size, session_id=_get_session_id()))


@app.route("/api/favorites/<int:qid>", methods=["POST", "DELETE"])
def api_toggle_favorite(qid):
    sid = _get_session_id()
    if request.method == "POST":
        tag = (request.get_json(silent=True) or {}).get("tag")
        added = db.toggle_favorite(qid, tag, session_id=sid)
        return jsonify({"favorited": added})
    else:
        removed = db.remove_favorite(qid, session_id=sid)
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
    import_result = db.batch_add_questions(result["questions"])
    response = {
        "added": import_result["added"],
        "skipped": import_result["skipped"],
        "total": len(result["questions"]),
    }
    if result["errors"]:
        response["parse_errors"] = result["errors"]
    return jsonify(response), 201


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
    """清除当前 session 的答题记录（统计、错题）"""
    try:
        db.reset_progress(session_id=_get_session_id())
        return jsonify({"ok": True, "message": "答题记录已清除"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    app.logger.exception("Server error")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # 检测弱默认 admin token
    if cfg["security"]["admin_enabled"] and cfg["security"].get("admin_token") == "local-admin-token":
        app.logger.warning("⚠ 使用默认 admin token 'local-admin-token'，请通过环境变量 QUIZ_ADMIN_TOKEN 设置强密码")
    app.run(host=cfg["server"]["host"], port=cfg["server"]["port"], debug=cfg["server"]["debug"])

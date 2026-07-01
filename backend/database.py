# -*- coding: utf-8 -*-
"""SQLite 数据层 - 统一后端"""
import sqlite3
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
import threading
import re as _re


def clean_stem(stem):
    """清理题干中的答案标注"""
    if not stem:
        return stem
    # 移除括号中的答案标注，如"（答案）" "（对）" "（A）"等
    # 匹配全角和半角括号
    stem = _re.sub(r'[（(]\s*(?:答案|答|对|错|[A-Da-d])\s*[）)]', '（　）', stem, flags=_re.IGNORECASE)
    # 移除题干末尾的答案标记，如"答案：XXX"
    stem = _re.sub(r'答案?\s*[:：]\s*\S+', '', stem, flags=_re.IGNORECASE)
    return stem.strip()


class QuizDatabase:
    def __init__(self, db_path: str, backup_dir: str = None):
        self.db_path = db_path
        self.backup_dir = backup_dir or str(Path(db_path).parent / "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        self._long_lived_conn = None
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self):
        if self._long_lived_conn is None:
            self._long_lived_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._long_lived_conn.row_factory = sqlite3.Row
            self._long_lived_conn.execute("PRAGMA journal_mode=WAL")
        return self._long_lived_conn

    def close(self):
        """关闭长连接，释放数据库文件锁"""
        if self._long_lived_conn is not None:
            try:
                self._long_lived_conn.close()
            except Exception:
                pass
            self._long_lived_conn = None

    def __del__(self):
        self.close()

    @contextmanager
    def connection(self):
        with self._lock:
            conn = self._conn()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _init_db(self):
        with self.connection() as conn:
            # 第一步：预迁移 - 为旧表添加 session_id 列（在创建索引之前）
            self._pre_migrate(conn)
            
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER,
                    course TEXT NOT NULL,
                    chapter INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    stem TEXT NOT NULL,
                    options_json TEXT NOT NULL DEFAULT '{}',
                    answer_json TEXT NOT NULL DEFAULT '[]',
                    explanation TEXT,
                    knowledge TEXT,
                    difficulty TEXT DEFAULT 'medium',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(course, stem)
                );
                CREATE INDEX IF NOT EXISTS idx_q_course ON questions(course);
                CREATE INDEX IF NOT EXISTS idx_q_chapter ON questions(chapter);
                CREATE INDEX IF NOT EXISTS idx_q_type ON questions(type);
                CREATE INDEX IF NOT EXISTS idx_q_knowledge ON questions(knowledge);

                CREATE TABLE IF NOT EXISTS answer_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    user_answer TEXT,
                    correct INTEGER NOT NULL DEFAULT 0,
                    elapsed_seconds INTEGER DEFAULT 0,
                    session_id TEXT NOT NULL DEFAULT 'legacy',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_ar_qid ON answer_records(question_id);
                CREATE INDEX IF NOT EXISTS idx_ar_correct ON answer_records(correct);
                CREATE INDEX IF NOT EXISTS idx_ar_session ON answer_records(session_id);

                CREATE TABLE IF NOT EXISTS mistakes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    wrong_count INTEGER DEFAULT 1,
                    last_wrong_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT NOT NULL DEFAULT 'legacy',
                    UNIQUE(question_id, session_id),
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_mistakes_session ON mistakes(session_id);

                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    tag TEXT,
                    session_id TEXT NOT NULL DEFAULT 'legacy',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(question_id, session_id),
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_fav_session ON favorites(session_id);

                CREATE TABLE IF NOT EXISTS exam_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    question_ids TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    duration INTEGER DEFAULT 0,
                    completed INTEGER DEFAULT 0,
                    score REAL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    nickname TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'student'
                        CHECK (role IN ('student', 'admin')),
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS rate_limits (
                    key TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    window_start TEXT NOT NULL,
                    PRIMARY KEY (key, window_start)
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reporter_id INTEGER,
                    session_id TEXT,
                    question_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    detail TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'resolved', 'dismissed')),
                    handled_by INTEGER,
                    handled_at TEXT,
                    admin_note TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_user_question
                ON reports(reporter_id, question_id) WHERE reporter_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
            """)
            # 第二步：后迁移 - 重建旧表以更新 UNIQUE 约束
            self._post_migrate(conn)
            # 第三步：迁移到 bank_id 架构
            self._migrate_to_banks(conn)
            # 第四步：为 answer_records/mistakes/favorites 添加 user_id 和 bank_id 列
            self._migrate_user_bank_columns(conn)

    def _pre_migrate(self, conn):
        """为旧版表添加 session_id 列（在 executescript 之前运行）"""
        for table in ('answer_records', 'mistakes', 'favorites'):
            try:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                if 'session_id' not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN session_id TEXT NOT NULL DEFAULT 'legacy'")
            except Exception:
                pass

    def _post_migrate(self, conn):
        """重建旧表以更新 UNIQUE 约束（mistakes/favorites 从 UNIQUE(question_id) 变为 UNIQUE(question_id, session_id)）"""
        for table, create_sql in [
            ('mistakes', "CREATE TABLE mistakes_new (id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER NOT NULL, wrong_count INTEGER DEFAULT 1, last_wrong_at TEXT DEFAULT CURRENT_TIMESTAMP, session_id TEXT NOT NULL DEFAULT 'legacy', UNIQUE(question_id, session_id), FOREIGN KEY (question_id) REFERENCES questions(id))"),
            ('favorites', "CREATE TABLE favorites_new (id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER NOT NULL, tag TEXT, session_id TEXT NOT NULL DEFAULT 'legacy', created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(question_id, session_id), FOREIGN KEY (question_id) REFERENCES questions(id))"),
        ]:
            try:
                schema = conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
                if schema and 'UNIQUE(question_id, session_id)' not in schema[0] and 'question_id' in schema[0]:
                    idx_name = f"idx_{table[:3]}_session"
                    conn.execute(f"DROP INDEX IF EXISTS {idx_name}")
                    conn.execute(create_sql)
                    if table == 'mistakes':
                        conn.execute("INSERT OR IGNORE INTO mistakes_new (id, question_id, wrong_count, last_wrong_at, session_id) SELECT id, question_id, wrong_count, last_wrong_at, COALESCE(session_id, 'legacy') FROM mistakes")
                    else:
                        conn.execute("INSERT OR IGNORE INTO favorites_new (id, question_id, tag, session_id, created_at) SELECT id, question_id, tag, COALESCE(session_id, 'legacy'), created_at FROM favorites")
                    conn.execute(f"DROP TABLE {table}")
                    conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
                    conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}(session_id)")
            except Exception:
                pass

    def _migrate_to_banks(self, conn):
        """Step 0 迁移：questions 表重建为 bank_id 架构 + 创建 question_banks 表"""
        # 检查是否已迁移
        cols = [r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()]
        if 'bank_id' in cols:
            # 已迁移，确保 question_banks 表和官方记录存在
            self._ensure_question_banks_table(conn)
            self._ensure_official_bank(conn)
            return

        # 1. 创建 question_banks 表（如果不存在）
        self._ensure_question_banks_table(conn)

        # 2. 记录旧表数据量
        old_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]

        # 3. 创建新表
        conn.execute("""
            CREATE TABLE questions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                bank_id INTEGER NOT NULL DEFAULT 1,
                course TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                type TEXT NOT NULL,
                stem TEXT NOT NULL,
                options_json TEXT,
                answer_json TEXT,
                explanation TEXT DEFAULT '',
                knowledge TEXT DEFAULT '',
                difficulty TEXT DEFAULT 'medium',
                flagged INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bank_id, stem),
                FOREIGN KEY (bank_id) REFERENCES question_banks(id)
            )
        """)

        # 4. 拷贝数据（bank_id 默认为 1 = 官方题库）
        conn.execute("""
            INSERT INTO questions_new (original_id, bank_id, course, chapter, type, stem,
                options_json, answer_json, explanation, knowledge, difficulty, created_at, updated_at)
            SELECT id, 1, course, chapter, type, stem,
                options_json, answer_json, explanation, knowledge, difficulty, created_at, updated_at
            FROM questions
        """)

        # 5. 校验数量
        new_count = conn.execute("SELECT COUNT(*) FROM questions_new").fetchone()[0]
        if new_count != old_count:
            raise RuntimeError(f"迁移数据量不一致: 旧={old_count}, 新={new_count}")

        # 6. 替换表
        conn.execute("DROP TABLE questions")
        conn.execute("ALTER TABLE questions_new RENAME TO questions")

        # 7. 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_q_course ON questions(course)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_q_chapter ON questions(chapter)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_q_type ON questions(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_q_knowledge ON questions(knowledge)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_bank_id ON questions(bank_id)")

        # 8. 插入官方题库记录（question_count 动态计算）
        self._ensure_official_bank(conn)

    def _ensure_question_banks_table(self, conn):
        """确保 question_banks 表存在"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS question_banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT NOT NULL,
                course TEXT NOT NULL,
                description TEXT DEFAULT '',
                visibility TEXT NOT NULL DEFAULT 'private'
                    CHECK (visibility IN ('private', 'public', 'unlisted')),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'hidden', 'deleted', 'reviewing')),
                question_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_question_banks_owner ON question_banks(owner_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_question_banks_visibility ON question_banks(visibility)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bank_subscriptions (
                user_id INTEGER NOT NULL,
                bank_id INTEGER NOT NULL,
                subscribed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, bank_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (bank_id) REFERENCES question_banks(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_subscriptions_user ON bank_subscriptions(user_id)")

    def _ensure_official_bank(self, conn):
        """确保官方题库记录存在（id=1, owner_id=NULL）"""
        row = conn.execute("SELECT 1 FROM question_banks WHERE id = 1").fetchone()
        if row is None:
            count = conn.execute("SELECT COUNT(*) FROM questions WHERE bank_id = 1").fetchone()[0]
            conn.execute("""
                INSERT INTO question_banks (id, owner_id, name, course, visibility, status, question_count)
                VALUES (1, NULL, '官方题库', 'weather', 'public', 'active', ?)
            """, (count,))
        else:
            # 更新 question_count
            count = conn.execute("SELECT COUNT(*) FROM questions WHERE bank_id = 1").fetchone()[0]
            conn.execute("UPDATE question_banks SET question_count = ? WHERE id = 1", (count,))

    def create_bank(self, owner_id: int, name: str, course: str,
                    description: str = '', visibility: str = 'private') -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """INSERT INTO question_banks (owner_id, name, course, description, visibility)
                VALUES (?, ?, ?, ?, ?)""",
                (owner_id, name, course, description, visibility)
            )
            return cur.lastrowid

    def get_bank(self, bank_id: int) -> dict:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM question_banks WHERE id = ?", (bank_id,)).fetchone()
        return dict(row) if row else None

    def list_banks(self, owner_id: int = None, visibility: str = None,
                   scope: str = None, user_id: int = None) -> list:
        with self.connection() as conn:
            if scope == 'official':
                rows = conn.execute(
                    "SELECT * FROM question_banks WHERE owner_id IS NULL AND status = 'active' ORDER BY id"
                ).fetchall()
            elif scope == 'mine' and owner_id:
                rows = conn.execute(
                    "SELECT * FROM question_banks WHERE owner_id = ? AND status != 'deleted' ORDER BY created_at DESC",
                    (owner_id,)
                ).fetchall()
            elif scope == 'public':
                rows = conn.execute(
                    "SELECT * FROM question_banks WHERE visibility = 'public' AND status = 'active' AND owner_id IS NOT NULL ORDER BY created_at DESC"
                ).fetchall()
            elif scope == 'subscribed' and user_id:
                rows = conn.execute(
                    """SELECT b.* FROM question_banks b
                    JOIN bank_subscriptions s ON b.id = s.bank_id
                    WHERE s.user_id = ? AND b.status = 'active'
                    ORDER BY s.subscribed_at DESC""",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM question_banks WHERE status != 'deleted' ORDER BY id"
                ).fetchall()
        return [dict(r) for r in rows]

    def delete_bank(self, bank_id: int) -> bool:
        with self.connection() as conn:
            cur = conn.execute("UPDATE question_banks SET status = 'deleted' WHERE id = ?", (bank_id,))
            return cur.rowcount > 0

    def update_bank(self, bank_id: int, data: dict) -> bool:
        allowed = {'name', 'course', 'description', 'visibility', 'status'}
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return False
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [bank_id]
        with self.connection() as conn:
            conn.execute(f"UPDATE question_banks SET {sets} WHERE id = ?", values)
            return True

    def update_bank_question_count(self, bank_id: int):
        with self.connection() as conn:
            conn.execute(
                "UPDATE question_banks SET question_count = (SELECT COUNT(*) FROM questions WHERE bank_id = ?) WHERE id = ?",
                (bank_id, bank_id)
            )

    def count_user_banks(self, owner_id: int) -> int:
        with self.connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM question_banks WHERE owner_id = ? AND status != 'deleted'",
                (owner_id,)
            ).fetchone()[0]

    def create_report(self, question_id: int, reason: str, detail: str = '',
                      reporter_id: int = None, session_id: str = None) -> int:
        """创建举报。已登录用户重复举报返回 None。"""
        try:
            with self.connection() as conn:
                cur = conn.execute(
                    """INSERT INTO reports (reporter_id, session_id, question_id, reason, detail)
                    VALUES (?, ?, ?, ?, ?)""",
                    (reporter_id, session_id, question_id, reason, detail)
                )
                return cur.lastrowid
        except sqlite3.IntegrityError:
            return None  # 重复举报

    def list_reports(self, status: str = None) -> list:
        """列出举报"""
        with self.connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM reports WHERE status = ? ORDER BY created_at DESC", (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reports ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def handle_report(self, report_id: int, status: str, admin_note: str = '',
                      handler_id: int = None) -> bool:
        """处理举报"""
        with self.connection() as conn:
            cur = conn.execute(
                """UPDATE reports SET status = ?, admin_note = ?, handled_by = ?, handled_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (status, admin_note, handler_id, report_id)
            )
            return cur.rowcount > 0

    def subscribe_bank(self, user_id: int, bank_id: int) -> bool:
        """订阅题库。返回 True 表示新订阅，False 表示已订阅。"""
        try:
            with self.connection() as conn:
                conn.execute(
                    "INSERT INTO bank_subscriptions (user_id, bank_id) VALUES (?, ?)",
                    (user_id, bank_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def unsubscribe_bank(self, user_id: int, bank_id: int) -> bool:
        """退订题库。"""
        with self.connection() as conn:
            cur = conn.execute(
                "DELETE FROM bank_subscriptions WHERE user_id = ? AND bank_id = ?",
                (user_id, bank_id)
            )
            return cur.rowcount > 0

    def backup(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(self.backup_dir, f"quiz_{ts}.db")
        shutil.copy2(self.db_path, dst)
        return dst

    def add_question(self, q: dict, bank_id: int = 1) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO questions
                (original_id, bank_id, course, chapter, type, stem, options_json, answer_json, explanation, knowledge)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    q.get("id"),
                    bank_id,
                    q.get("course"),
                    q.get("chapter"),
                    q.get("type"),
                    q.get("stem"),
                    json.dumps(q.get("options", {}), ensure_ascii=False),
                    json.dumps(q.get("answer"), ensure_ascii=False),
                    q.get("explanation", ""),
                    q.get("knowledge", ""),
                ),
            )
            return cur.lastrowid

    def batch_add_questions(self, questions: list, bank_id: int = 1) -> dict:
        """批量添加题目，利用 UNIQUE(bank_id, stem) 自动去重。

        Args:
            questions: 题目字典列表
            bank_id: 所属题库 ID，默认为 1（官方题库）

        Returns:
            {added: int, skipped: int}
        """
        added = 0
        skipped = 0
        with self.connection() as conn:
            for q in questions:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO questions
                    (original_id, bank_id, course, chapter, type, stem, options_json, answer_json, explanation, knowledge, flagged)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        q.get("id"),
                        bank_id,
                        q.get("course"),
                        q.get("chapter"),
                        q.get("type"),
                        q.get("stem"),
                        json.dumps(q.get("options", {}), ensure_ascii=False),
                        json.dumps(q.get("answer"), ensure_ascii=False),
                        q.get("explanation", ""),
                        q.get("knowledge", ""),
                        1 if q.get("_flagged") else 0,
                    ),
                )
                if cur.rowcount > 0:
                    added += 1
                else:
                    skipped += 1
        return {"added": added, "skipped": skipped}

    def search_questions(
        self,
        course: str = None,
        chapter: int = None,
        qtype: str = None,
        keyword: str = None,
        knowledge: str = None,
        page: int = 1,
        page_size: int = 20,
        bank_id: int = None,
    ) -> dict:
        where = ["1=1"]
        params = []
        if bank_id is not None:
            where.append("bank_id = ?")
            params.append(bank_id)
        if course:
            where.append("course = ?")
            params.append(course)
        if chapter is not None:
            where.append("chapter = ?")
            params.append(chapter)
        if qtype:
            # 支持多题型（逗号分隔，如 "single,multiple"）
            types = [t.strip() for t in qtype.split(",") if t.strip()]
            if len(types) == 1:
                where.append("type = ?")
                params.append(types[0])
            elif len(types) > 1:
                placeholders = ",".join(["?"] * len(types))
                where.append(f"type IN ({placeholders})")
                params.extend(types)
        if knowledge:
            where.append("knowledge = ?")
            params.append(knowledge)
        if keyword:
            where.append("stem LIKE ? ESCAPE '\\'")
            # 转义 LIKE 通配符
            escaped = keyword.replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")

        clause = " AND ".join(where)
        offset = (page - 1) * page_size

        with self.connection() as conn:
            conn.execute("PRAGMA case_sensitive_like = OFF")
            total = conn.execute(f"SELECT COUNT(*) FROM questions WHERE {clause}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM questions WHERE {clause} ORDER BY id LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()

        items = []
        for r in rows:
            item = self._row_to_dict(r)
            item['stem'] = clean_stem(item.get('stem', ''))
            items.append(item)
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_question(self, qid: int) -> dict:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
        return self._row_to_dict(row) if row else None

    def get_chapters(self, course: str = None) -> dict:
        """获取各课程（或指定课程）的章节列表"""
        with self.connection() as conn:
            if course:
                rows = conn.execute(
                    "SELECT DISTINCT chapter FROM questions WHERE course = ? ORDER BY chapter",
                    (course,)
                ).fetchall()
                return {"course": course, "chapters": [r[0] for r in rows]}
            else:
                rows = conn.execute(
                    "SELECT course, GROUP_CONCAT(DISTINCT chapter) as chapters "
                    "FROM questions GROUP BY course"
                ).fetchall()
                result = {}
                for r in rows:
                    chapters = sorted([int(x) for x in r[1].split(",")]) if r[1] else []
                    result[r[0]] = chapters
                return result

    def get_random_questions(self, course: str = None, chapter: int = None, qtype: str = None, limit: int = 20, bank_id: int = None) -> list:
        where = ["1=1"]
        params = []
        if bank_id is not None:
            where.append("bank_id = ?")
            params.append(bank_id)
        if course:
            where.append("course = ?")
            params.append(course)
        if chapter is not None:
            where.append("chapter = ?")
            params.append(chapter)
        if qtype:
            # 支持多题型（逗号分隔）
            types = [t.strip() for t in qtype.split(",") if t.strip()]
            if len(types) == 1:
                where.append("type = ?")
                params.append(types[0])
            elif len(types) > 1:
                placeholders = ",".join(["?"] * len(types))
                where.append(f"type IN ({placeholders})")
                params.extend(types)
        clause = " AND ".join(where)
        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM questions WHERE {clause} ORDER BY RANDOM() LIMIT ?",
                params + [limit],
            ).fetchall()
        results = [self._row_to_dict(r) for r in rows]
        for q in results:
            q['stem'] = clean_stem(q.get('stem', ''))
        return results

    def record_answer(self, question_id: int, user_answer, correct: bool, elapsed: int = 0,
                      session_id: str = 'anon', user_id: int = None, bank_id: int = 1):
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO answer_records (question_id, user_answer, correct, elapsed_seconds, session_id, user_id, bank_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (question_id, json.dumps(user_answer, ensure_ascii=False), int(correct), elapsed, session_id, user_id, bank_id),
            )
            if correct:
                if user_id:
                    conn.execute("DELETE FROM mistakes WHERE question_id = ? AND (session_id = ? OR user_id = ?)",
                                 (question_id, session_id, user_id))
                else:
                    conn.execute("DELETE FROM mistakes WHERE question_id = ? AND session_id = ?", (question_id, session_id))
            else:
                if user_id:
                    conn.execute(
                        """INSERT INTO mistakes (question_id, wrong_count, last_wrong_at, session_id, user_id, bank_id)
                        VALUES (?, 1, CURRENT_TIMESTAMP, ?, ?, ?)
                        ON CONFLICT(question_id, session_id) DO UPDATE SET
                        wrong_count = wrong_count + 1, last_wrong_at = CURRENT_TIMESTAMP""",
                        (question_id, session_id, user_id, bank_id),
                    )
                else:
                    conn.execute(
                        """INSERT INTO mistakes (question_id, wrong_count, last_wrong_at, session_id, bank_id)
                        VALUES (?, 1, CURRENT_TIMESTAMP, ?, ?)
                        ON CONFLICT(question_id, session_id) DO UPDATE SET
                        wrong_count = wrong_count + 1, last_wrong_at = CURRENT_TIMESTAMP""",
                        (question_id, session_id, bank_id),
                    )

    def get_stats(self, session_id: str = 'anon', user_id: int = None, bank_id: int = None) -> dict:
        with self.connection() as conn:
            if bank_id:
                total = conn.execute("SELECT COUNT(*) FROM questions WHERE bank_id = ?", (bank_id,)).fetchone()[0]
                if user_id:
                    answered = conn.execute("SELECT COUNT(DISTINCT ar.question_id) FROM answer_records ar JOIN questions q ON ar.question_id = q.id WHERE ar.user_id = ? AND q.bank_id = ?", (user_id, bank_id)).fetchone()[0]
                    correct = conn.execute("SELECT COUNT(*) FROM answer_records ar JOIN questions q ON ar.question_id = q.id WHERE ar.correct = 1 AND ar.user_id = ? AND q.bank_id = ?", (user_id, bank_id)).fetchone()[0]
                    total_answers = conn.execute("SELECT COUNT(*) FROM answer_records ar JOIN questions q ON ar.question_id = q.id WHERE ar.user_id = ? AND q.bank_id = ?", (user_id, bank_id)).fetchone()[0]
                    mistake_count = conn.execute("SELECT COUNT(*) FROM mistakes m JOIN questions q ON m.question_id = q.id WHERE m.user_id = ? AND q.bank_id = ?", (user_id, bank_id)).fetchone()[0]
                    fav_count = conn.execute("SELECT COUNT(*) FROM favorites f JOIN questions q ON f.question_id = q.id WHERE f.user_id = ? AND q.bank_id = ?", (user_id, bank_id)).fetchone()[0]
                    answered_ids = [r[0] for r in conn.execute(
                        "SELECT DISTINCT ar.question_id FROM answer_records ar JOIN questions q ON ar.question_id = q.id WHERE ar.user_id = ? AND q.bank_id = ?",
                        (user_id, bank_id)
                    ).fetchall()]
                else:
                    answered = conn.execute("SELECT COUNT(DISTINCT ar.question_id) FROM answer_records ar JOIN questions q ON ar.question_id = q.id WHERE ar.session_id = ? AND q.bank_id = ?", (session_id, bank_id)).fetchone()[0]
                    correct = conn.execute("SELECT COUNT(*) FROM answer_records ar JOIN questions q ON ar.question_id = q.id WHERE ar.correct = 1 AND ar.session_id = ? AND q.bank_id = ?", (session_id, bank_id)).fetchone()[0]
                    total_answers = conn.execute("SELECT COUNT(*) FROM answer_records ar JOIN questions q ON ar.question_id = q.id WHERE ar.session_id = ? AND q.bank_id = ?", (session_id, bank_id)).fetchone()[0]
                    mistake_count = conn.execute("SELECT COUNT(*) FROM mistakes m JOIN questions q ON m.question_id = q.id WHERE m.session_id = ? AND q.bank_id = ?", (session_id, bank_id)).fetchone()[0]
                    fav_count = conn.execute("SELECT COUNT(*) FROM favorites f JOIN questions q ON f.question_id = q.id WHERE f.session_id = ? AND q.bank_id = ?", (session_id, bank_id)).fetchone()[0]
                    answered_ids = [r[0] for r in conn.execute(
                        "SELECT DISTINCT ar.question_id FROM answer_records ar JOIN questions q ON ar.question_id = q.id WHERE ar.session_id = ? AND q.bank_id = ?",
                        (session_id, bank_id)
                    ).fetchall()]
                type_dist = conn.execute("SELECT type, COUNT(*) FROM questions WHERE bank_id = ? GROUP BY type", (bank_id,)).fetchall()
                course_dist = conn.execute("SELECT course, COUNT(*) FROM questions WHERE bank_id = ? GROUP BY course", (bank_id,)).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
                if user_id:
                    answered = conn.execute("SELECT COUNT(DISTINCT question_id) FROM answer_records WHERE user_id = ?", (user_id,)).fetchone()[0]
                    correct = conn.execute("SELECT COUNT(*) FROM answer_records WHERE correct = 1 AND user_id = ?", (user_id,)).fetchone()[0]
                    total_answers = conn.execute("SELECT COUNT(*) FROM answer_records WHERE user_id = ?", (user_id,)).fetchone()[0]
                    mistake_count = conn.execute("SELECT COUNT(*) FROM mistakes WHERE user_id = ?", (user_id,)).fetchone()[0]
                    fav_count = conn.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)).fetchone()[0]
                    answered_ids = [r[0] for r in conn.execute(
                        "SELECT DISTINCT question_id FROM answer_records WHERE user_id = ?", (user_id,)
                    ).fetchall()]
                else:
                    answered = conn.execute("SELECT COUNT(DISTINCT question_id) FROM answer_records WHERE session_id = ?", (session_id,)).fetchone()[0]
                    correct = conn.execute("SELECT COUNT(*) FROM answer_records WHERE correct = 1 AND session_id = ?", (session_id,)).fetchone()[0]
                    total_answers = conn.execute("SELECT COUNT(*) FROM answer_records WHERE session_id = ?", (session_id,)).fetchone()[0]
                    mistake_count = conn.execute("SELECT COUNT(*) FROM mistakes WHERE session_id = ?", (session_id,)).fetchone()[0]
                    fav_count = conn.execute("SELECT COUNT(*) FROM favorites WHERE session_id = ?", (session_id,)).fetchone()[0]
                    answered_ids = [r[0] for r in conn.execute(
                        "SELECT DISTINCT question_id FROM answer_records WHERE session_id = ?", (session_id,)
                    ).fetchall()]
                type_dist = conn.execute("SELECT type, COUNT(*) FROM questions GROUP BY type").fetchall()
                course_dist = conn.execute("SELECT course, COUNT(*) FROM questions GROUP BY course").fetchall()
        return {
            "total_questions": total,
            "answered_questions": answered,
            "answered_question_ids": answered_ids,
            "total_answers": total_answers,
            "correct_answers": correct,
            "accuracy": round(correct / total_answers, 4) if total_answers else 0,
            "mistake_count": mistake_count,
            "favorite_count": fav_count,
            "type_distribution": {r[0]: r[1] for r in type_dist},
            "course_distribution": {r[0]: r[1] for r in course_dist},
        }

    def get_mistakes(self, page=1, page_size=20, session_id='anon', user_id=None):
        offset = (page - 1) * page_size
        with self.connection() as conn:
            if user_id:
                total = conn.execute("SELECT COUNT(*) FROM mistakes WHERE user_id = ?", (user_id,)).fetchone()[0]
                rows = conn.execute(
                    """SELECT q.*, m.wrong_count, m.last_wrong_at
                    FROM questions q JOIN mistakes m ON q.id = m.question_id
                    WHERE m.user_id = ?
                    ORDER BY m.wrong_count DESC, m.last_wrong_at DESC
                    LIMIT ? OFFSET ?""",
                    (user_id, page_size, offset),
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) FROM mistakes WHERE session_id = ?", (session_id,)).fetchone()[0]
                rows = conn.execute(
                    """SELECT q.*, m.wrong_count, m.last_wrong_at
                    FROM questions q JOIN mistakes m ON q.id = m.question_id
                    WHERE m.session_id = ?
                    ORDER BY m.wrong_count DESC, m.last_wrong_at DESC
                    LIMIT ? OFFSET ?""",
                    (session_id, page_size, offset),
                ).fetchall()
        return {"items": [self._row_to_dict(r) for r in rows], "page": page, "page_size": page_size, "total": total}

    def get_favorites(self, page=1, page_size=20, session_id='anon', user_id=None):
        offset = (page - 1) * page_size
        with self.connection() as conn:
            if user_id:
                total = conn.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)).fetchone()[0]
                rows = conn.execute(
                    """SELECT q.*, f.tag, f.created_at as fav_at
                    FROM questions q JOIN favorites f ON q.id = f.question_id
                    WHERE f.user_id = ?
                    ORDER BY f.created_at DESC LIMIT ? OFFSET ?""",
                    (user_id, page_size, offset),
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) FROM favorites WHERE session_id = ?", (session_id,)).fetchone()[0]
                rows = conn.execute(
                    """SELECT q.*, f.tag, f.created_at as fav_at
                    FROM questions q JOIN favorites f ON q.id = f.question_id
                    WHERE f.session_id = ?
                    ORDER BY f.created_at DESC LIMIT ? OFFSET ?""",
                    (session_id, page_size, offset),
                ).fetchall()
        return {"items": [self._row_to_dict(r) for r in rows], "page": page, "page_size": page_size, "total": total}

    def toggle_favorite(self, question_id: int, tag: str = None, session_id: str = 'anon', user_id: int = None, bank_id: int = 1):
        with self.connection() as conn:
            if user_id:
                exists = conn.execute("SELECT 1 FROM favorites WHERE question_id = ? AND user_id = ?", (question_id, user_id)).fetchone()
                if exists:
                    conn.execute("DELETE FROM favorites WHERE question_id = ? AND user_id = ?", (question_id, user_id))
                    return False
                else:
                    conn.execute("INSERT INTO favorites (question_id, tag, session_id, user_id, bank_id) VALUES (?, ?, ?, ?, ?)",
                                 (question_id, tag, session_id, user_id, bank_id))
                    return True
            else:
                exists = conn.execute("SELECT 1 FROM favorites WHERE question_id = ? AND session_id = ?", (question_id, session_id)).fetchone()
                if exists:
                    conn.execute("DELETE FROM favorites WHERE question_id = ? AND session_id = ?", (question_id, session_id))
                    return False
                else:
                    conn.execute("INSERT INTO favorites (question_id, tag, session_id) VALUES (?, ?, ?)", (question_id, tag, session_id))
                    return True

    def remove_favorite(self, question_id: int, session_id: str = 'anon', user_id: int = None) -> bool:
        """幂等删除收藏：未收藏时不创建收藏。"""
        with self.connection() as conn:
            if user_id:
                cur = conn.execute("DELETE FROM favorites WHERE question_id = ? AND user_id = ?", (question_id, user_id))
            else:
                cur = conn.execute("DELETE FROM favorites WHERE question_id = ? AND session_id = ?", (question_id, session_id))
            return cur.rowcount > 0

    def reset_progress(self, session_id: str = 'anon', user_id: int = None):
        """清除指定 session 或 user 的答题记录（含统计与错题）"""
        with self.connection() as conn:
            if user_id:
                conn.execute("DELETE FROM answer_records WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM mistakes WHERE user_id = ?", (user_id,))
            else:
                conn.execute("DELETE FROM answer_records WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM mistakes WHERE session_id = ?", (session_id,))
            conn.commit()

    def delete_question(self, qid: int):
        with self.connection() as conn:
            conn.execute("DELETE FROM answer_records WHERE question_id = ?", (qid,))
            conn.execute("DELETE FROM mistakes WHERE question_id = ?", (qid,))
            conn.execute("DELETE FROM favorites WHERE question_id = ?", (qid,))
            cur = conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
            return cur.rowcount > 0

    def update_question(self, qid: int, data: dict):
        allowed = {"stem", "options_json", "answer_json", "explanation", "knowledge", "difficulty", "chapter", "type"}
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return False
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [qid]
        with self.connection() as conn:
            conn.execute(f"UPDATE questions SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
            return True

    def get_all_for_export(self):
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM questions ORDER BY course, chapter, id").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def deduplicate(self):
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT id, course, stem FROM questions
                WHERE id NOT IN (
                    SELECT MIN(id) FROM questions GROUP BY course, stem
                )
            """).fetchall()
            removed = 0
            for r in rows:
                conn.execute("DELETE FROM answer_records WHERE question_id = ?", (r[0],))
                conn.execute("DELETE FROM mistakes WHERE question_id = ?", (r[0],))
                conn.execute("DELETE FROM favorites WHERE question_id = ?", (r[0],))
                conn.execute("DELETE FROM questions WHERE id = ?", (r[0],))
                removed += 1
            return removed

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        d["options"] = json.loads(d.pop("options_json", "{}"))
        d["answer"] = json.loads(d.pop("answer_json", "[]"))
        return d

    def create_user(self, student_id: str, password_hash: str, nickname: str) -> int:
        """创建用户。成功返回 user_id，学号重复返回 None。"""
        try:
            with self.connection() as conn:
                cur = conn.execute(
                    "INSERT INTO users (student_id, password_hash, nickname) VALUES (?, ?, ?)",
                    (student_id, password_hash, nickname)
                )
                return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def get_user_by_student_id(self, student_id: str) -> dict:
        """按学号查询用户（含密码哈希，用于登录验证）"""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE student_id = ?", (student_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict:
        """按 ID 查询用户（不含密码哈希）"""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, student_id, nickname, role, created_at FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def _migrate_user_bank_columns(self, conn):
        """为 answer_records/mistakes/favorites 添加 user_id 和 bank_id 列"""
        for table in ('answer_records', 'mistakes', 'favorites'):
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if 'user_id' not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")
            if 'bank_id' not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN bank_id INTEGER")
        # 防重复唯一索引
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_fav_user_question
            ON favorites(user_id, question_id) WHERE user_id IS NOT NULL
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mistakes_user_question
            ON mistakes(user_id, question_id) WHERE user_id IS NOT NULL
        """)
        # 复合索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_answer_records_user_bank ON answer_records(user_id, bank_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mistakes_user_bank ON mistakes(user_id, bank_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user_bank ON favorites(user_id, bank_id)")

    def migrate_session_data(self, user_id: int, session_id: str):
        """将匿名 session_id 数据迁移到 user_id。幂等可重复执行。"""
        with self.connection() as conn:
            # answer_records: 迁移不重复的记录
            conn.execute("""
                UPDATE answer_records SET user_id=?
                WHERE session_id=? AND user_id IS NULL
                AND question_id NOT IN (
                    SELECT question_id FROM answer_records WHERE user_id=?
                )
            """, (user_id, session_id, user_id))

            # favorites: 迁移不重复的收藏
            conn.execute("""
                UPDATE favorites SET user_id=?
                WHERE session_id=? AND user_id IS NULL
                AND question_id NOT IN (
                    SELECT question_id FROM favorites WHERE user_id=?
                )
            """, (user_id, session_id, user_id))

            # mistakes: 同理
            conn.execute("""
                UPDATE mistakes SET user_id=?
                WHERE session_id=? AND user_id IS NULL
                AND question_id NOT IN (
                    SELECT question_id FROM mistakes WHERE user_id=?
                )
            """, (user_id, session_id, user_id))

            # 清理重复的匿名数据（未能迁移的重复记录仍为匿名，删除之）
            conn.execute("DELETE FROM answer_records WHERE session_id=? AND user_id IS NULL", (session_id,))
            conn.execute("DELETE FROM favorites WHERE session_id=? AND user_id IS NULL", (session_id,))
            conn.execute("DELETE FROM mistakes WHERE session_id=? AND user_id IS NULL", (session_id,))

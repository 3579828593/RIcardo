# -*- coding: utf-8 -*-
"""SQLite 数据层 - 统一后端"""
import sqlite3
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager


class QuizDatabase:
    def __init__(self, db_path: str, backup_dir: str = None):
        self.db_path = db_path
        self.backup_dir = backup_dir or str(Path(db_path).parent / "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def connection(self):
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self.connection() as conn:
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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_ar_qid ON answer_records(question_id);
                CREATE INDEX IF NOT EXISTS idx_ar_correct ON answer_records(correct);

                CREATE TABLE IF NOT EXISTS mistakes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL UNIQUE,
                    wrong_count INTEGER DEFAULT 1,
                    last_wrong_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL UNIQUE,
                    tag TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                );

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
            """)

    def backup(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(self.backup_dir, f"quiz_{ts}.db")
        shutil.copy2(self.db_path, dst)
        return dst

    def add_question(self, q: dict) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO questions
                (original_id, course, chapter, type, stem, options_json, answer_json, explanation, knowledge)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    q.get("id"),
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

    def search_questions(
        self,
        course: str = None,
        chapter: int = None,
        qtype: str = None,
        keyword: str = None,
        knowledge: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        where = ["1=1"]
        params = []
        if course:
            where.append("course = ?")
            params.append(course)
        if chapter is not None:
            where.append("chapter = ?")
            params.append(chapter)
        if qtype:
            where.append("type = ?")
            params.append(qtype)
        if knowledge:
            where.append("knowledge = ?")
            params.append(knowledge)
        if keyword:
            where.append("stem LIKE ?")
            params.append(f"%{keyword}%")

        clause = " AND ".join(where)
        offset = (page - 1) * page_size

        with self.connection() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM questions WHERE {clause}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM questions WHERE {clause} ORDER BY id LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()

        items = []
        for r in rows:
            items.append(self._row_to_dict(r))
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_question(self, qid: int) -> dict:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
        return self._row_to_dict(row) if row else None

    def get_random_questions(self, course: str = None, chapter: int = None, qtype: str = None, limit: int = 20) -> list:
        where = ["1=1"]
        params = []
        if course:
            where.append("course = ?")
            params.append(course)
        if chapter is not None:
            where.append("chapter = ?")
            params.append(chapter)
        if qtype:
            where.append("type = ?")
            params.append(qtype)
        clause = " AND ".join(where)
        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM questions WHERE {clause} ORDER BY RANDOM() LIMIT ?",
                params + [limit],
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def record_answer(self, question_id: int, user_answer, correct: bool, elapsed: int = 0):
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO answer_records (question_id, user_answer, correct, elapsed_seconds) VALUES (?, ?, ?, ?)",
                (question_id, json.dumps(user_answer, ensure_ascii=False), int(correct), elapsed),
            )
            if correct:
                conn.execute("DELETE FROM mistakes WHERE question_id = ?", (question_id,))
            else:
                conn.execute(
                    """INSERT INTO mistakes (question_id, wrong_count, last_wrong_at)
                    VALUES (?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(question_id) DO UPDATE SET
                    wrong_count = wrong_count + 1, last_wrong_at = CURRENT_TIMESTAMP""",
                    (question_id,),
                )

    def get_stats(self) -> dict:
        with self.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            answered = conn.execute("SELECT COUNT(DISTINCT question_id) FROM answer_records").fetchone()[0]
            correct = conn.execute("SELECT COUNT(*) FROM answer_records WHERE correct = 1").fetchone()[0]
            total_answers = conn.execute("SELECT COUNT(*) FROM answer_records").fetchone()[0]
            mistake_count = conn.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0]
            fav_count = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
            type_dist = conn.execute("SELECT type, COUNT(*) FROM questions GROUP BY type").fetchall()
            course_dist = conn.execute("SELECT course, COUNT(*) FROM questions GROUP BY course").fetchall()
        return {
            "total_questions": total,
            "answered_questions": answered,
            "total_answers": total_answers,
            "correct_answers": correct,
            "accuracy": round(correct / total_answers, 4) if total_answers else 0,
            "mistake_count": mistake_count,
            "favorite_count": fav_count,
            "type_distribution": {r[0]: r[1] for r in type_dist},
            "course_distribution": {r[0]: r[1] for r in course_dist},
        }

    def get_mistakes(self, page=1, page_size=20):
        offset = (page - 1) * page_size
        with self.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0]
            rows = conn.execute(
                """SELECT q.*, m.wrong_count, m.last_wrong_at
                FROM questions q JOIN mistakes m ON q.id = m.question_id
                ORDER BY m.wrong_count DESC, m.last_wrong_at DESC
                LIMIT ? OFFSET ?""",
                (page_size, offset),
            ).fetchall()
        return {"items": [self._row_to_dict(r) for r in rows], "page": page, "page_size": page_size, "total": total}

    def get_favorites(self, page=1, page_size=20):
        offset = (page - 1) * page_size
        with self.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
            rows = conn.execute(
                """SELECT q.*, f.tag, f.created_at as fav_at
                FROM questions q JOIN favorites f ON q.id = f.question_id
                ORDER BY f.created_at DESC LIMIT ? OFFSET ?""",
                (page_size, offset),
            ).fetchall()
        return {"items": [self._row_to_dict(r) for r in rows], "page": page, "page_size": page_size, "total": total}

    def toggle_favorite(self, question_id: int, tag: str = None):
        with self.connection() as conn:
            exists = conn.execute("SELECT 1 FROM favorites WHERE question_id = ?", (question_id,)).fetchone()
            if exists:
                conn.execute("DELETE FROM favorites WHERE question_id = ?", (question_id,))
                return False
            else:
                conn.execute("INSERT INTO favorites (question_id, tag) VALUES (?, ?)", (question_id, tag))
                return True

    def remove_favorite(self, question_id: int) -> bool:
        """幂等删除收藏：未收藏时不创建收藏。"""
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM favorites WHERE question_id = ?", (question_id,))
            return cur.rowcount > 0

    def delete_question(self, qid: int):
        with self.connection() as conn:
            conn.execute("DELETE FROM answer_records WHERE question_id = ?", (qid,))
            conn.execute("DELETE FROM mistakes WHERE question_id = ?", (qid,))
            conn.execute("DELETE FROM favorites WHERE question_id = ?", (qid,))
            conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
            return conn.total_changes > 0

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

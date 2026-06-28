#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据迁移工具：quiz-data.js → SQLite，支持导入/导出/去重/校验"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from database import QuizDatabase


def normalize_answer(qtype: str, raw):
    """统一答案格式为 list"""
    if qtype in ("多选题", "multiple"):
        if isinstance(raw, list):
            return sorted(raw)
        return [str(raw)]
    if qtype in ("单选题", "词汇单选题", "single"):
        if isinstance(raw, list):
            return raw[:1]
        return [str(raw)]
    if qtype in ("判断题", "true_false"):
        if isinstance(raw, list):
            return raw[:1]
        return [str(raw)]
    # 填空/简答
    if isinstance(raw, list):
        return raw
    return [str(raw)]


def normalize_type(t: str) -> str:
    mapping = {
        "单选题": "single",
        "多选题": "multiple",
        "判断题": "true_false",
        "填空题": "fill_blank",
        "简答题": "short_answer",
        "词汇单选题": "single",
    }
    return mapping.get(t, t)


def import_js(js_path: str, db_path: str):
    print(f"[导入] {js_path} → {db_path}")
    db = QuizDatabase(db_path)
    db.backup()

    with open(js_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # 提取 QUIZ_DATA
    end_idx = raw.find("\nconst COURSES =")
    if end_idx == -1:
        end_idx = len(raw)
    quiz_part = raw[:end_idx]
    m = re.search(r'const\s+QUIZ_DATA\s*=\s*(\{.*?\});?\s*$', quiz_part, re.DOTALL)
    if not m:
        print("错误：无法解析 QUIZ_DATA")
        sys.exit(1)

    data = json.loads(m.group(1))
    total = 0
    skipped = 0
    for course, questions in data.items():
        for q in questions:
            q["course"] = course
            q["type"] = normalize_type(q.get("type", "single"))
            q["answer"] = normalize_answer(q.get("type", "single"), q.get("correct"))
            q["chapter"] = int(q.get("chapter", 1))
            rid = db.add_question(q)
            if rid:
                total += 1
            else:
                skipped += 1
    print(f"[完成] 导入 {total} 题，跳过重复 {skipped} 题")
    stats = db.get_stats()
    print(f"[统计] 总题数: {stats['total_questions']}")


def export_json(db_path: str, out_path: str):
    print(f"[导出] {db_path} → {out_path}")
    db = QuizDatabase(db_path)
    items = db.get_all_for_export()
    out = {}
    for it in items:
        c = it["course"]
        out.setdefault(c, [])
        out[c].append(it)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[完成] 导出 {len(items)} 题")


def dedupe(db_path: str):
    print(f"[去重] {db_path}")
    db = QuizDatabase(db_path)
    db.backup()
    removed = db.deduplicate()
    print(f"[完成] 删除重复 {removed} 题")


def validate(db_path: str):
    print(f"[校验] {db_path}")
    db = QuizDatabase(db_path)
    stats = db.get_stats()
    print(f"  总题数: {stats['total_questions']}")
    print(f"  题型分布: {stats['type_distribution']}")
    print(f"  课程分布: {stats['course_distribution']}")
    print(f"  已答题数: {stats['total_answers']}")
    print(f"  正确率: {stats['accuracy']:.2%}")
    print(f"  错题数: {stats['mistake_count']}")
    print(f"  收藏数: {stats['favorite_count']}")


def main():
    parser = argparse.ArgumentParser(description="题库数据迁移工具")
    parser.add_argument("--db", default="data/quiz.db", help="SQLite 数据库路径")
    sub = parser.add_subparsers(dest="cmd")

    p_import = sub.add_parser("import-js", help="从 quiz-data.js 导入")
    p_import.add_argument("input", help="quiz-data.js 路径")

    p_export = sub.add_parser("export-json", help="导出为 JSON")
    p_export.add_argument("output", help="输出 JSON 路径")

    sub.add_parser("dedupe", help="去重")
    sub.add_parser("validate", help="校验统计")

    args = parser.parse_args()
    db_path = str(Path(__file__).parent / args.db)

    if args.cmd == "import-js":
        import_js(args.input, db_path)
    elif args.cmd == "export-json":
        export_json(db_path, args.output)
    elif args.cmd == "dedupe":
        dedupe(db_path)
    elif args.cmd == "validate":
        validate(db_path)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

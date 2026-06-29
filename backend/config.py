# -*- coding: utf-8 -*-
"""配置加载模块"""
import os
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DEFAULT_CONFIG = {
    "server": {"host": "127.0.0.1", "port": 5000, "debug": False, "workers": 1},
    "storage": {"db_path": "data/quiz.db", "backup_dir": "data/backups", "export_json_path": "data/questions.json"},
    "quiz": {"default_page_size": 20, "max_page_size": 100, "shuffle": False, "time_limit_minutes": 0},
    "security": {"admin_enabled": True, "admin_token_env": "QUIZ_ADMIN_TOKEN", "secret_key_env": "SECRET_KEY", "rate_limit_per_minute": 60},
    "logging": {"level": "INFO", "file": "logs/app.log", "max_bytes": 10485760, "backup_count": 5},
}


def load_config():
    config_path = BASE_DIR.parent / "config.yaml"
    cfg = dict(DEFAULT_CONFIG)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        _deep_update(cfg, user_cfg)
    # 环境变量覆盖
    cfg["server"]["host"] = os.environ.get("HOST", cfg["server"]["host"])
    cfg["server"]["port"] = int(os.environ.get("PORT", cfg["server"]["port"]))
    cfg["security"]["secret_key"] = os.environ.get(cfg["security"]["secret_key_env"], "dev-change-me-" + str(os.urandom(16).hex()))
    cfg["security"]["admin_token"] = os.environ.get(cfg["security"]["admin_token_env"])
    # 路径绝对化（支持 RENDER 或 DATA_DIR 环境变量覆盖数据目录）
    data_dir = os.environ.get("DATA_DIR", str(BASE_DIR))
    for k in ["db_path", "backup_dir", "export_json_path"]:
        cfg["storage"][k] = str(Path(data_dir) / cfg["storage"][k])
    log_dir = os.environ.get("LOG_DIR", str(BASE_DIR))
    cfg["logging"]["file"] = str(Path(log_dir) / cfg["logging"]["file"])
    # 确保目录存在
    for p in [cfg["storage"]["db_path"], cfg["storage"]["backup_dir"], cfg["logging"]["file"]]:
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    return cfg


def _deep_update(base, overlay):
    for k, v in overlay.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_update(base[k], v)
        else:
            base[k] = v

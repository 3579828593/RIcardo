#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""桌面启动器：后台线程运行 Flask，主线程运行 pywebview 窗口。

设计要点：
- 复用 backend/app.py 中的 ``app`` 对象，不重复实现业务逻辑。
- 通过 ``sys.path`` 注入 backend 目录，使 ``import app`` 直接加载源文件，
  这样 ``app.py`` / ``config.py`` 中基于 ``__file__`` 的路径解析在打包后
  依然能正确定位 templates / static / data / config.yaml。
- Flask 运行在守护线程中（使用 werkzeug 的 make_server，无 reloader）；
  pywebview 必须运行在主线程（Windows GUI 要求）。
- 窗口关闭后调用 ``server.shutdown()`` 优雅停止 Flask；守护线程作为兜底。
- 设置环境变量 ``QUIZ_NO_GUI=1`` 可进入无界面模式（仅启动 Flask），
  便于自动化验证打包后的 exe。
"""
import os
import sys
import time
import threading
import traceback
import urllib.request
from pathlib import Path


def _resource_base() -> Path:
    """返回资源根目录：打包后为 ``sys._MEIPASS``，开发模式为脚本所在目录。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.resolve()


def _ensure_stdio() -> None:
    """windowed 模式下 sys.stdout/stderr 可能为 None，重定向到 devnull 以防 print 崩溃。"""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")


def _bootstrap_backend() -> Path:
    """把 backend 目录加入 sys.path，返回该目录。"""
    backend_dir = _resource_base() / "backend"
    sys.path.insert(0, str(backend_dir))
    return backend_dir


def _wait_for_server(url: str, timeout: float = 20.0) -> bool:
    """轮询直到 Flask 返回 200 或超时。"""
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.2)
    if last_err:
        sys.stderr.write(f"等待 Flask 启动失败: {last_err}\n")
    return False


def _start_flask(flask_app, host: str = "127.0.0.1", port: int = 5000):
    """以守护线程方式启动 Flask（复用 app 对象，无 reloader）。返回 (server, url)。"""
    from werkzeug.serving import make_server

    server = None
    used_port = port
    # 优先使用指定端口；若被占用则自动尝试后续端口，保证可启动。
    for try_port in range(port, port + 20):
        try:
            server = make_server(host, try_port, flask_app, threaded=True)
            used_port = try_port
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError(f"无法在 {host}:{port}-{port + 19} 上绑定 Flask 服务")

    flask_thread = threading.Thread(
        target=server.serve_forever, name="FlaskServer", daemon=True
    )
    flask_thread.start()
    return server, f"http://{host}:{used_port}", flask_thread


def main() -> int:
    _ensure_stdio()
    backend_dir = _bootstrap_backend()

    # 复用 app.py 的 app 对象（从 backend/app.py 文件加载，保证 __file__ 路径正确）
    import app as app_module  # noqa: E402
    flask_app = app_module.app

    server, url, flask_thread = _start_flask(flask_app, host="127.0.0.1", port=5000)

    # 无界面模式：仅运行 Flask，便于自动化验证 exe
    if os.environ.get("QUIZ_NO_GUI"):
        sys.stdout.write(f"[QUIZ_NO_GUI] Flask running on {url}\n")
        sys.stdout.flush()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            try:
                server.shutdown()
            except Exception:  # noqa: BLE001
                pass
        return 0

    # 等待 Flask 就绪后再打开窗口，避免首屏加载失败
    if not _wait_for_server(url):
        sys.stderr.write(f"Flask 未在 {url} 就绪，仍尝试打开窗口。\n")

    import webview

    webview.create_window("期末冲刺刷题系统", url, width=1000, height=700)
    webview.start()  # 阻塞主线程，直到窗口关闭

    # 窗口关闭后停止 Flask
    try:
        server.shutdown()
    except Exception:  # noqa: BLE001
        pass
    flask_thread.join(timeout=3)
    return 0


def _write_crash_log(exc_text: str) -> None:
    try:
        log_dir = Path(os.environ.get("TEMP") or os.path.expanduser("~"))
        log_path = log_dir / "quiz_desktop_error.log"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("=" * 60 + "\n")
            fh.write(exc_text + "\n")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        _write_crash_log(traceback.format_exc())
        raise

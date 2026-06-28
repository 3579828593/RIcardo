# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：将 Flask + Vue 刷题系统打包为 Windows 单文件 exe。

打包产物：dist/期末冲刺刷题系统.exe  (onefile, windowed)

资源映射（运行时布局，保证 backend/app.py 与 backend/config.py 中
基于 ``__file__`` 的路径解析在打包后依然正确）：

    <_MEIPASS>/
        config.yaml                 <- config.py 读取 BASE_DIR.parent / config.yaml
        desktop_app.py              (入口，编译进 PYZ)
        backend/
            app.py                  <- 以数据文件形式打包，运行时从文件加载
            config.py                  （不进 PYZ，避免 __file__ 指向 _MEIPASS 根
            database.py                 导致 config.yaml / data / templates 路径错乱）
            data_migration.py
            templates/               <- app.py 的 template_folder
            static/                  <- app.py 的 static_folder
            data/quiz.db             <- SQLite 数据库（351 题）
            logs/                    <- 运行时创建
"""

from pathlib import Path

block_cipher = None

# spec 文件位于项目根目录 d:\期末冲刺刷题系统\
PROJECT_DIR = Path(SPECPATH).resolve()
BACKEND_DIR = PROJECT_DIR / 'backend'

# ---- 数据文件 (datas) ----
# backend 源码以「数据文件」形式打包，运行时通过 sys.path 从文件加载，
# 以保证 __file__ 指向 <_MEIPASS>/backend/xxx.py，路径逻辑与源码一致。
backend_modules = ['app.py', 'config.py', 'database.py', 'data_migration.py']

datas = []
for mod in backend_modules:
    src = BACKEND_DIR / mod
    datas.append((str(src), 'backend'))

# 前端与数据资源
datas += [
    (str(BACKEND_DIR / 'templates'), 'backend/templates'),
    (str(BACKEND_DIR / 'static'), 'backend/static'),
    (str(BACKEND_DIR / 'data'), 'backend/data'),
    (str(PROJECT_DIR / 'config.yaml'), '.'),
]

# ---- 隐式导入 (hiddenimports) ----
# backend/app.py 等以数据文件形式打包，PyInstaller 不会静态分析其导入，
# 因此需显式声明其第三方依赖。flask 的 hook 会自动带上 werkzeug/jinja2 等，
# 但 werkzeug.serving（make_server 所在）需显式声明。
# pywebview 在 Windows 上动态导入 webview.platforms.winforms，必须显式声明。
hiddenimports = [
    # Flask 生态
    'flask', 'flask.json', 'flask.cli', 'flask.templating', 'flask.helpers',
    'werkzeug', 'werkzeug.serving', 'werkzeug.routing', 'werkzeug.middleware',
    'jinja2', 'jinja2.ext', 'jinja2._identifier',
    'click', 'click.exceptions',
    'itsdangerous', 'markupsafe',
    # 配置
    'yaml',
    # pywebview（pip 发行名 pywebview，导入名 webview；Windows -> winforms -> edgechromium/win32；clr/pythonnet 由 hook 收集）
    'webview', 'webview.guilib', 'webview.menu', 'webview.screen',
    'webview.util', 'webview.window', 'webview.event',
    'webview.platforms.winforms', 'webview.platforms.edgechromium',
    'webview.platforms.win32', 'webview.platforms.mshtml',
    # 标准库（显式声明以稳妥）
    'sqlite3', 'logging.handlers', 'hmac', 'functools',
]

# ---- 排除 (excludes) ----
# backend 自有模块不进 PYZ（以数据文件形式提供，运行时从文件加载）；
# 排除测试相关模块。
excludes = [
    'app', 'config', 'database', 'data_migration',  # 由 datas 提供，避免进 PYZ
    'tests', 'pytest', 'ui_smoke',                   # 测试文件
    'gunicorn',                                      # 生产服务器，桌面端不需要
    'matplotlib', 'numpy', 'pandas', 'tkinter',      # 未使用，减小体积
]

a = Analysis(
    ['desktop_app.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onefile：把 binaries/datas/zipfiles 全部并入 EXE，不使用 COLLECT
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='期末冲刺刷题系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # 桌面应用：无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

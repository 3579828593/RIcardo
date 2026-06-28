@echo off
chcp 65001 >nul
REM ============================================================
REM 期末冲刺刷题系统 · Windows 一键启动
REM ============================================================

echo ═══════════════════════════════════════════════
echo   期末冲刺刷题系统 · 本地启动
echo   课程：天气分析与预报方法 + 大学英语II
echo ═══════════════════════════════════════════════
echo.

cd /d "%~dp0\.."

REM 检查 Node.js
where node >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Node.js。请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org
    pause
    exit /b 1
)

for /f "tokens=1 delims=." %%a in ('node -v') do set NODE_VER=%%a
set NODE_VER=%NODE_VER:v=%
if %NODE_VER% LSS 18 (
    echo [错误] Node.js 版本过低，需要 18+
    pause
    exit /b 1
)

echo [✓] Node.js 版本: 
node -v

set PORT=3000
if not "%1"=="" set PORT=%1
echo [✓] 启动端口: %PORT%

if not exist ".next\standalone" (
    echo [错误] 未找到构建产物 .next\standalone
    echo 请先运行: bun run build 或 npm run build
    pause
    exit /b 1
)

if not exist ".next\standalone\.next\static" (
    echo [!] 复制静态资源...
    xcopy /E /I /Y .next\static .next\standalone\.next\static >nul
)
if not exist ".next\standalone\public" (
    xcopy /E /I /Y public .next\standalone\public >nul
)

echo.
echo [✓] 启动中...
echo.
echo ═══════════════════════════════════════════════
echo   浏览器访问: http://localhost:%PORT%
echo   按 Ctrl+C 停止服务
echo ═══════════════════════════════════════════════
echo.

cd .next\standalone
set PORT=%PORT%
set HOSTNAME=0.0.0.0
node server.js

pause

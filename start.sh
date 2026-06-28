#!/usr/bin/env bash
# ============================================================
# 天气分析与预报方法 + 大学英语II 期末冲刺刷题系统
# 一键启动脚本 (Linux/macOS)
# ============================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  期末冲刺刷题系统 · 本地启动${NC}"
echo -e "${BLUE}  课程：天气分析与预报方法 + 大学英语II${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

cd "$(dirname "$0")/.."

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}[错误] 未检测到 Node.js。请先安装 Node.js 18+ (https://nodejs.org)${NC}"
    exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}[错误] Node.js 版本过低 (当前: $(node -v))，需要 18+${NC}"
    exit 1
fi

echo -e "${GREEN}[✓]${NC} Node.js 版本: $(node -v)"

PORT=${1:-3000}
echo -e "${GREEN}[✓]${NC} 启动端口: $PORT"

if [ ! -d ".next/standalone" ]; then
    echo -e "${RED}[错误] 未找到构建产物 .next/standalone${NC}"
    echo -e "${YELLOW}请先在项目根目录运行: bun run build 或 npm run build${NC}"
    exit 1
fi

# 复制静态资源
if [ ! -d ".next/standalone/.next/static" ]; then
    echo -e "${YELLOW}[!] 复制静态资源...${NC}"
    cp -r .next/static .next/standalone/.next/
fi
if [ ! -d ".next/standalone/public" ]; then
    cp -r public .next/standalone/
fi

echo ""
echo -e "${GREEN}[✓]${NC} 启动中..."
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  浏览器访问: http://localhost:${PORT}${NC}"
echo -e "${YELLOW}  按 Ctrl+C 停止服务${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════${NC}"
echo ""

cd .next/standalone
PORT=$PORT HOSTNAME=0.0.0.0 node server.js

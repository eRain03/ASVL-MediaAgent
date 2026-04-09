#!/bin/bash
# ASVL 停止脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo "停止 ASVL 服务..."
echo ""

# 停止前端
if [ -f logs/frontend.pid ]; then
    PID=$(cat logs/frontend.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        log_info "前端服务已停止 (PID: $PID)"
    fi
    rm -f logs/frontend.pid
else
    # 尝试通过端口停止
    if lsof -ti :3000 > /dev/null 2>&1; then
        lsof -ti :3000 | xargs kill -9 2>/dev/null || true
        log_info "前端服务已停止 (端口 3000)"
    fi
fi

# 停止 Celery Worker
if [ -f logs/worker.pid ]; then
    PID=$(cat logs/worker.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        # 等待进程结束
        sleep 2
        # 如果还在运行，强制停止
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID" 2>/dev/null || true
        fi
        log_info "Celery Worker 已停止 (PID: $PID)"
    fi
    rm -f logs/worker.pid
else
    # 尝试通过进程名停止
    pkill -f "celery.*asvl.workers" 2>/dev/null || true
fi

# 停止 API 服务
if [ -f logs/api.pid ]; then
    PID=$(cat logs/api.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        log_info "API 服务已停止 (PID: $PID)"
    fi
    rm -f logs/api.pid
else
    # 尝试通过端口停止
    if lsof -ti :8000 > /dev/null 2>&1; then
        lsof -ti :8000 | xargs kill -9 2>/dev/null || true
        log_info "API 服务已停止 (端口 8000)"
    fi
fi

echo ""
log_info "✓ 所有服务已停止"
echo ""

# 可选：停止数据库和 Redis
read -p "是否停止 PostgreSQL 和 Redis? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker stop asvl-postgres asvl-redis 2>/dev/null || true
    log_info "PostgreSQL 和 Redis 已停止"
fi

echo ""
log_info "完成"
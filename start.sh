#!/bin/bash
# ASVL 一键启动脚本
# 使用方法: ./start.sh [--docker] [--skip-deps]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}==>${NC} $1"
}

# 解析参数
USE_DOCKER=false
SKIP_DEPS=false

for arg in "$@"; do
    case $arg in
        --docker)
            USE_DOCKER=true
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --help)
            echo "使用方法: ./start.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --docker      使用 Docker 启动所有服务"
            echo "  --skip-deps   跳过依赖安装"
            echo "  --help        显示帮助信息"
            exit 0
            ;;
    esac
done

# Docker 模式
if [ "$USE_DOCKER" = true ]; then
    log_step "使用 Docker Compose 启动所有服务..."

    if ! command -v docker-compose &> /dev/null; then
        log_error "未找到 docker-compose，请先安装 Docker"
        exit 1
    fi

    docker-compose up -d

    echo ""
    log_info "服务已启动:"
    echo "  - 前端: http://localhost:3000"
    echo "  - 后端: http://localhost:8000"
    echo "  - API文档: http://localhost:8000/docs"
    echo ""
    log_info "查看日志: docker-compose logs -f"
    log_info "停止服务: docker-compose down"
    exit 0
fi

# 本地开发模式
log_step "ASVL 本地开发环境启动"
echo ""

# 1. 检查依赖
log_step "检查系统依赖..."

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "未找到 $1，请先安装"
        return 1
    fi
    log_info "✓ $1 已安装"
}

# 检查 Python
check_command "python3" || exit 1
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
log_info "  Python 版本: $PYTHON_VERSION"

# 检查 Node.js
check_command "node" || exit 1
NODE_VERSION=$(node --version 2>&1)
log_info "  Node.js 版本: $NODE_VERSION"

# 检查 FFmpeg
check_command "ffmpeg" || exit 1
check_command "ffprobe" || exit 1

# 检查 PostgreSQL
if ! command -v psql &> /dev/null; then
    log_warn "未找到 psql，假设 PostgreSQL 运行在 Docker 中"
fi

# 检查 Redis
if ! command -v redis-cli &> /dev/null; then
    log_warn "未找到 redis-cli，假设 Redis 运行在 Docker 中"
fi

echo ""

# 2. 启动 PostgreSQL 和 Redis (Docker)
log_step "启动基础服务 (PostgreSQL, Redis)..."

# 检查是否已有容器运行
DB_RUNNING=$(docker ps --filter "name=asvl-postgres" --filter "status=running" -q 2>/dev/null || true)
REDIS_RUNNING=$(docker ps --filter "name=asvl-redis" --filter "status=running" -q 2>/dev/null || true)

if [ -z "$DB_RUNNING" ]; then
    log_info "启动 PostgreSQL..."
    docker run -d \
        --name asvl-postgres \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -e POSTGRES_DB=asvl \
        -p 5432:5432 \
        -v asvl_postgres_data:/var/lib/postgresql/data \
        postgres:15-alpine > /dev/null 2>&1 || {
            # 容器可能已存在但未运行
            docker start asvl-postgres > /dev/null 2>&1 || true
        }
    sleep 2
fi
log_info "✓ PostgreSQL 运行中 (端口 5432)"

if [ -z "$REDIS_RUNNING" ]; then
    log_info "启动 Redis..."
    docker run -d \
        --name asvl-redis \
        -p 6379:6379 \
        -v asvl_redis_data:/data \
        redis:7-alpine > /dev/null 2>&1 || {
            docker start asvl-redis > /dev/null 2>&1 || true
        }
    sleep 1
fi
log_info "✓ Redis 运行中 (端口 6379)"

echo ""

# 3. 安装 Python 依赖
if [ "$SKIP_DEPS" = false ]; then
    log_step "检查 Python 依赖..."

    if [ ! -d "venv" ]; then
        log_info "创建虚拟环境..."
        python3 -m venv venv
    fi

    source venv/bin/activate

    # 检查是否需要更新依赖
    if ! pip show fastapi &> /dev/null; then
        log_info "安装 Python 依赖..."
        pip install -e . -q
    else
        log_info "✓ Python 依赖已安装"
    fi
else
    source venv/bin/activate
fi

echo ""

# 4. 初始化数据库
log_step "检查数据库连接..."

# 等待数据库就绪
for i in {1..10}; do
    if docker exec asvl-postgres pg_isready -U postgres > /dev/null 2>&1; then
        log_info "✓ 数据库连接正常"
        break
    fi
    if [ $i -eq 10 ]; then
        log_error "数据库连接失败"
        exit 1
    fi
    sleep 1
done

# 创建数据库表（如果不存在）
log_info "初始化数据库表..."
python3 -c "
from asvl.db.session import engine, Base
from asvl.db.models import VideoTask, ASRResult, SegmentResult, ClipResult, VLResult, FinalOutput
import asyncio

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('数据库表初始化完成')

asyncio.run(init_db())
" 2>/dev/null || log_warn "数据库表可能已存在"

echo ""

# 5. 创建必要目录
log_step "创建工作目录..."
mkdir -p temp/audio temp/frames videos clips logs
log_info "✓ 目录创建完成"

echo ""

# 6. 启动后端服务
log_step "启动后端服务..."

# 检查端口是否被占用
if lsof -i :8000 > /dev/null 2>&1; then
    log_warn "端口 8000 已被占用，尝试停止..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# 启动 API 服务 (后台运行)
nohup uvicorn asvl.main:app --host 0.0.0.0 --port 8000 --reload > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > logs/api.pid
log_info "✓ API 服务启动 (PID: $API_PID)"

sleep 2

# 检查 API 是否启动成功
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    log_warn "API 服务启动中，请稍候..."
fi

echo ""

# 7. 启动 Celery Worker
log_step "启动 Celery Worker..."

# 检查端口是否被占用
if lsof -i :5555 > /dev/null 2>&1; then
    log_warn "端口 5555 已被占用"
fi

# 启动 Worker (后台运行)
nohup celery -A asvl.workers.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    -Q asr,llm,clip,vl,fusion,default \
    > logs/worker.log 2>&1 &
WORKER_PID=$!
echo $WORKER_PID > logs/worker.pid
log_info "✓ Celery Worker 启动 (PID: $WORKER_PID)"

echo ""

# 8. 安装前端依赖
cd frontend

if [ "$SKIP_DEPS" = false ]; then
    log_step "检查前端依赖..."

    if [ ! -d "node_modules" ]; then
        log_info "安装前端依赖..."
        npm install --silent
    else
        log_info "✓ 前端依赖已安装"
    fi
fi

echo ""

# 9. 启动前端服务
log_step "启动前端服务..."

# 检查端口是否被占用
if lsof -i :3000 > /dev/null 2>&1; then
    log_warn "端口 3000 已被占用，尝试停止..."
    lsof -ti :3000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# 启动前端 (后台运行)
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid
log_info "✓ 前端服务启动 (PID: $FRONTEND_PID)"

cd "$PROJECT_ROOT"

echo ""
echo "========================================"
log_info "🎉 ASVL 服务启动完成!"
echo "========================================"
echo ""
echo "服务地址:"
echo "  • 前端:     http://localhost:3000"
echo "  • 后端API:  http://localhost:8000"
echo "  • API文档:  http://localhost:8000/docs"
echo "  • 健康检查: http://localhost:8000/health"
echo ""
echo "日志文件:"
echo "  • API:    logs/api.log"
echo "  • Worker: logs/worker.log"
echo "  • 前端:   logs/frontend.log"
echo ""
echo "停止服务: ./stop.sh"
echo "查看日志: tail -f logs/api.log"
echo ""
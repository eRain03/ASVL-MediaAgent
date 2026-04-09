#!/bin/bash
# ASVL 状态检查脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_service() {
    local name=$1
    local port=$2
    local url=$3

    if lsof -i :$port > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name 运行中 (端口 $port)"
        if [ -n "$url" ]; then
            response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
            if [ "$response" = "200" ]; then
                echo -e "  └─ 健康检查: ${GREEN}OK${NC}"
            else
                echo -e "  └─ 健康检查: ${YELLOW}HTTP $response${NC}"
            fi
        fi
    else
        echo -e "${RED}✗${NC} $name 未运行"
    fi
}

check_docker() {
    local name=$1
    if docker ps --filter "name=$name" --filter "status=running" -q > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name (Docker) 运行中"
    else
        echo -e "${RED}✗${NC} $name (Docker) 未运行"
    fi
}

echo "========================================"
echo "ASVL 服务状态"
echo "========================================"
echo ""

echo "核心服务:"
check_service "前端" 3000 "http://localhost:3000"
check_service "后端API" 8000 "http://localhost:8000/health"
check_service "Celery Worker" - - 2>/dev/null || {
    if pgrep -f "celery.*asvl" > /dev/null; then
        echo -e "${GREEN}✓${NC} Celery Worker 运行中"
    else
        echo -e "${RED}✗${NC} Celery Worker 未运行"
    fi
}

echo ""
echo "基础服务:"
check_docker "asvl-postgres"
check_docker "asvl-redis"

echo ""
echo "========================================"

# 显示最近的日志
if [ -f logs/api.log ]; then
    echo ""
    echo "最近 API 日志:"
    echo "----------------------------------------"
    tail -5 logs/api.log 2>/dev/null || echo "(日志为空)"
fi
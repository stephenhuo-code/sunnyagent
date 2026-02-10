#!/bin/bash
# Sunnyagent 服务管理脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  start       启动所有服务 (PostgreSQL + 迁移 + 后端)"
    echo "  stop        停止所有服务 (清理沙箱 + 停止 PostgreSQL)"
    echo "  restart     重启所有服务"
    echo "  infra       启动基础设施 (仅 PostgreSQL)"
    echo "  infra-stop  停止基础设施"
    echo "  status      查看服务状态"
    echo "  logs        查看 PostgreSQL 日志"
    echo "  reset-admin 重置 admin 密码为 .env 中的 ADMIN_PASSWORD"
    echo "  clean       清理所有容器和数据卷 (危险操作)"
    echo ""
    echo "Examples:"
    echo "  $0 start      # 一键启动"
    echo "  $0 infra      # 仅启动数据库"
    echo "  $0 status     # 查看状态"
}

wait_for_postgres() {
    echo -e "${YELLOW}⏳ Waiting for PostgreSQL to be ready...${NC}"
    local max_attempts=30
    local attempt=0
    until docker-compose exec -T postgres pg_isready -U sunnyagent -d sunnyagent > /dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            echo -e "${RED}❌ PostgreSQL failed to start${NC}"
            exit 1
        fi
        sleep 1
    done
    echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
}

cmd_start() {
    echo -e "${GREEN}🚀 Starting Sunnyagent...${NC}"

    # 启动 PostgreSQL
    echo -e "${YELLOW}📦 Starting PostgreSQL...${NC}"
    docker-compose up -d postgres
    wait_for_postgres

    # 运行数据库迁移
    echo -e "${YELLOW}🔄 Running database migrations...${NC}"
    uv run alembic -c infra/alembic.ini upgrade head

    # 启动后端
    echo -e "${GREEN}🖥️  Starting backend server on port 8008...${NC}"
    echo "   Press Ctrl+C to stop"
    echo ""
    uv run uvicorn backend.main:app --reload --port 8008
}

cmd_stop() {
    echo -e "${YELLOW}🛑 Stopping Sunnyagent...${NC}"

    # 清理沙箱容器
    echo -e "${YELLOW}🧹 Cleaning up sandbox containers...${NC}"
    docker ps -a --filter "label=com.docker.compose.project=sunnyagent" \
                 --filter "label=com.docker.compose.service=sandbox" \
                 --format "{{.ID}}" | xargs -r docker rm -f 2>/dev/null || true

    # 停止 PostgreSQL
    echo -e "${YELLOW}📦 Stopping PostgreSQL...${NC}"
    docker-compose down

    echo -e "${GREEN}✅ All services stopped${NC}"
}

cmd_restart() {
    cmd_stop
    echo ""
    cmd_start
}

cmd_infra() {
    echo -e "${GREEN}📦 Starting infrastructure...${NC}"
    docker-compose up -d postgres
    wait_for_postgres

    # 运行数据库迁移
    echo -e "${YELLOW}🔄 Running database migrations...${NC}"
    uv run alembic -c infra/alembic.ini upgrade head

    echo ""
    echo -e "${GREEN}✅ Infrastructure ready${NC}"
    echo ""
    echo "Connection info:"
    echo "  Host: localhost:5432"
    echo "  Database: sunnyagent"
    echo "  User: sunnyagent"
    echo ""
    echo "Next step:"
    echo "  uv run uvicorn backend.main:app --reload --port 8008     # Start backend"
}

cmd_infra_stop() {
    echo -e "${YELLOW}📦 Stopping infrastructure...${NC}"
    docker-compose down
    echo -e "${GREEN}✅ Infrastructure stopped${NC}"
    echo ""
    echo "Note: Data volume 'sunnyagent-pgdata' is preserved"
}

cmd_status() {
    echo -e "${GREEN}📊 Service Status${NC}"
    echo ""

    # PostgreSQL 状态 (检查 "Up" 而非 "running")
    if docker-compose ps postgres 2>/dev/null | grep -q "Up"; then
        echo -e "PostgreSQL: ${GREEN}Running${NC}"
    else
        echo -e "PostgreSQL: ${RED}Stopped${NC}"
    fi

    # 沙箱容器数量
    sandbox_count=$(docker ps --filter "label=com.docker.compose.project=sunnyagent" \
                              --filter "label=com.docker.compose.service=sandbox" \
                              --format "{{.ID}}" | wc -l | tr -d ' ')
    echo -e "Sandbox containers: ${YELLOW}${sandbox_count}${NC}"

    echo ""
    echo "All sunnyagent containers:"
    docker ps --filter "label=com.docker.compose.project=sunnyagent" \
              --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  None"
}

cmd_logs() {
    docker-compose logs -f postgres
}

cmd_reset_admin() {
    echo -e "${YELLOW}🔑 Resetting admin password...${NC}"
    uv run python scripts/reset_admin.py
}

cmd_clean() {
    echo -e "${RED}⚠️  WARNING: This will delete ALL data including the database!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled"
        exit 0
    fi

    echo -e "${YELLOW}🧹 Cleaning up everything...${NC}"

    # 停止并删除所有容器
    docker ps -a --filter "label=com.docker.compose.project=sunnyagent" \
                 --format "{{.ID}}" | xargs -r docker rm -f 2>/dev/null || true

    # 删除数据卷
    docker-compose down -v 2>/dev/null || true

    echo -e "${GREEN}✅ All containers and volumes removed${NC}"
}

# 主入口
case "${1:-}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    infra)
        cmd_infra
        ;;
    infra-stop)
        cmd_infra_stop
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    reset-admin)
        cmd_reset_admin
        ;;
    clean)
        cmd_clean
        ;;
    -h|--help|help|"")
        usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        usage
        exit 1
        ;;
esac

#!/bin/bash
#
# SunnyAgent 启动脚本
#
# 用法:
#   ./scripts/start.sh          # 启动所有服务（infra + backend + frontend）
#   ./scripts/start.sh infra    # 只启动基础设施（PostgreSQL + Langfuse）
#   ./scripts/start.sh backend  # 只启动后端
#   ./scripts/start.sh frontend # 只启动前端
#   ./scripts/start.sh dev      # 启动开发环境（infra + backend + frontend）
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 启动基础设施（PostgreSQL + ClickHouse + Redis + MinIO + Langfuse v3）
start_infra() {
    log_info "启动基础设施服务..."

    # 检查 Docker 是否运行
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker 未运行，请先启动 Docker"
        exit 1
    fi

    # 启动所有基础设施服务
    log_info "启动 PostgreSQL, ClickHouse, Redis, MinIO..."
    docker compose up -d postgres clickhouse redis minio

    # 等待 PostgreSQL 就绪
    log_info "等待 PostgreSQL 就绪..."
    until docker compose exec -T postgres pg_isready -U sunnyagent > /dev/null 2>&1; do
        sleep 1
    done
    log_success "PostgreSQL 已就绪"

    # 检查 langfuse 数据库是否存在，不存在则创建
    if ! docker compose exec -T postgres psql -U sunnyagent -lqt | cut -d \| -f 1 | grep -qw langfuse; then
        log_info "创建 langfuse 数据库..."
        docker compose exec -T postgres psql -U sunnyagent -c "CREATE DATABASE langfuse;" || true
    fi

    # 等待 ClickHouse 就绪
    log_info "等待 ClickHouse 就绪..."
    until docker compose exec -T clickhouse clickhouse-client --user clickhouse --password clickhouse123 --query "SELECT 1" > /dev/null 2>&1; do
        sleep 1
    done
    log_success "ClickHouse 已就绪"

    # 等待 Redis 就绪
    log_info "等待 Redis 就绪..."
    until docker compose exec -T redis redis-cli -a redis123 ping > /dev/null 2>&1; do
        sleep 1
    done
    log_success "Redis 已就绪"

    # 等待 MinIO 就绪
    log_info "等待 MinIO 就绪..."
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:9090/minio/health/live > /dev/null 2>&1; then
            log_success "MinIO 已就绪"
            break
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    # 启动 Langfuse (Web + Worker)
    log_info "启动 Langfuse v3 (Web + Worker)..."
    docker compose up -d langfuse-worker langfuse

    # 等待 Langfuse 就绪
    log_info "等待 Langfuse 就绪（可能需要 60-120 秒）..."
    max_attempts=90
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:3001/api/public/health > /dev/null 2>&1; then
            log_success "Langfuse 已就绪: http://localhost:3001"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    if [ $attempt -eq $max_attempts ]; then
        log_warn "Langfuse 启动超时，请检查日志: docker compose logs langfuse"
    fi

    # 运行数据库迁移
    log_info "运行数据库迁移..."
    cd infra && uv run alembic upgrade head && cd ..
    log_success "数据库迁移完成"

    # 显示服务状态
    echo ""
    log_info "基础设施服务状态:"
    docker compose ps
}

# 启动后端
start_backend() {
    log_info "启动后端服务..."

    # 检查 .env 文件
    if [ ! -f ".env" ]; then
        log_warn ".env 文件不存在，复制 .env.example..."
        cp .env.example .env 2>/dev/null || log_warn "请手动创建 .env 文件"
    fi

    # 安装依赖
    log_info "安装 Python 依赖..."
    uv sync

    # 启动后端
    log_info "启动 FastAPI 后端 (port 8008)..."
    uv run uvicorn backend.main:app --reload --port 8008
}

# 启动前端
start_frontend() {
    log_info "启动前端服务..."

    cd frontend

    # 安装依赖
    if [ ! -d "node_modules" ]; then
        log_info "安装前端依赖..."
        npm install
    fi

    # 启动前端
    log_info "启动 Vite 开发服务器 (port 3008)..."
    npm run dev
}

# 启动开发环境（所有服务）
start_dev() {
    log_info "启动完整开发环境..."

    # 启动基础设施
    start_infra

    echo ""
    log_info "基础设施已就绪，请在新终端中启动应用服务:"
    echo ""
    echo "  # 终端 1 - 后端"
    echo "  ./scripts/start.sh backend"
    echo ""
    echo "  # 终端 2 - 前端"
    echo "  ./scripts/start.sh frontend"
    echo ""
    log_info "或使用以下命令在后台启动:"
    echo ""
    echo "  # 后端（后台运行）"
    echo "  nohup uv run uvicorn backend.main:app --reload --port 8008 > backend.log 2>&1 &"
    echo ""
    echo "  # 前端（后台运行）"
    echo "  cd frontend && nohup npm run dev > ../frontend.log 2>&1 &"
}

# 停止所有服务
stop_all() {
    log_info "停止所有服务..."
    docker compose down
    # 杀掉后端和前端进程（如果有）
    pkill -f "uvicorn backend.main:app" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    log_success "所有服务已停止"
}

# 显示帮助
show_help() {
    echo "SunnyAgent 启动脚本"
    echo ""
    echo "用法: ./scripts/start.sh [命令]"
    echo ""
    echo "命令:"
    echo "  infra     启动基础设施（PostgreSQL + ClickHouse + Redis + MinIO + Langfuse v3）"
    echo "  backend   启动后端服务"
    echo "  frontend  启动前端服务"
    echo "  dev       启动开发环境（infra + 提示）"
    echo "  stop      停止所有服务"
    echo "  help      显示帮助"
    echo ""
    echo "示例:"
    echo "  ./scripts/start.sh infra    # 启动所有基础设施服务"
    echo "  ./scripts/start.sh backend  # 启动后端 API"
    echo "  ./scripts/start.sh dev      # 启动完整开发环境"
}

# 主函数
main() {
    case "${1:-dev}" in
        infra)
            start_infra
            ;;
        backend)
            start_backend
            ;;
        frontend)
            start_frontend
            ;;
        dev)
            start_dev
            ;;
        stop)
            stop_all
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"

#!/bin/bash
set -e

echo "======================================"
echo "  此刻校园 - 一键部署/更新脚本"
echo "======================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env.prod ]; then
    echo "❌ 未找到 .env.prod 文件"
    echo "   如果是首次部署，请先运行 ./init.sh"
    exit 1
fi

source .env.prod

echo "🔄 拉取最新代码（如果是Git仓库）..."
if [ -d ../.git ]; then
    cd ..
    git pull
    cd "$SCRIPT_DIR"
fi

echo ""
echo "🏗️  重新构建并启动服务..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

echo ""
echo "⏳ 等待服务启动..."
sleep 10

echo ""
echo "📊 执行数据库迁移（如果有新迁移）..."
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic upgrade head || {
    echo "⚠️  数据库迁移跳过（无新迁移或迁移失败）"
}

echo ""
echo "======================================"
echo "✅ 部署完成！"
echo "======================================"
echo ""
echo "📱 访问地址：https://$DOMAIN"
echo "📋 查看服务状态：docker compose -f docker-compose.prod.yml ps"
echo "📝 查看日志：docker compose -f docker-compose.prod.yml logs -f"
echo ""

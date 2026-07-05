#!/bin/bash
set -e

echo "======================================"
echo "  此刻校园 - 服务器初始化脚本"
echo "======================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env.prod ]; then
    echo "❌ 未找到 .env.prod 文件"
    echo "   请先复制 .env.prod.example 为 .env.prod 并修改配置"
    echo "   cp .env.prod.example .env.prod"
    echo "   然后编辑 .env.prod 填入你的域名和密钥"
    exit 1
fi

source .env.prod

echo "📦 检查 Docker 和 Docker Compose..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    echo "   Ubuntu/Debian: curl -fsSL https://get.docker.com | sh"
    echo "   安装后执行: sudo usermod -aG docker \$USER && newgrp docker"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 未安装"
    exit 1
fi

echo "✅ Docker 环境检查通过"
echo ""

echo "📂 创建必要目录..."
mkdir -p nginx/conf.d
mkdir -p nginx/certbot/conf
mkdir -p nginx/certbot/www
mkdir -p ../backend/uploads
echo "✅ 目录创建完成"
echo ""

echo "🐳 加载 openGauss 镜像（如果本地没有）..."
if ! docker image inspect opengauss:7.0.0-RC3 &> /dev/null; then
    echo "⚠️  未找到 opengauss:7.0.0-RC3 镜像"
    echo "   请先从 openGauss 官网下载镜像并导入："
    echo "   1. 访问 https://opengauss.org/zh/download/ 下载 7.0.0-RC3 轻量版"
    echo "   2. docker load -i openGauss-7.0.0-RC3轻量版.tar"
    echo ""
    read -p "是否继续？(y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "⚙️  配置 Nginx（初始化模式，用于申请证书）..."
sed "s/YOUR_DOMAIN.COM/$DOMAIN/g" nginx/moment.conf.init > nginx/conf.d/moment.conf
echo "✅ Nginx 初始化配置已生成（域名: $DOMAIN）"
echo ""

echo "🚀 启动基础服务（openGauss + backend + frontend + nginx）..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d opengauss
echo "⏳ 等待 openGauss 启动（约30秒）..."
sleep 30

echo ""
echo "📊 执行数据库迁移..."
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend sh -c "
    python -c '
import asyncio
from app.database import engine
from app.models import Base
async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(init())
    '
" || echo "⚠️  自动建表尝试失败，将使用 Alembic 迁移"

docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic upgrade head || {
    echo "❌ 数据库迁移失败"
    echo "   如果是首次部署，可以继续，seed_data.py 会自动建表"
}

echo ""
echo "🌱 填充演示数据（江南大学蠡湖校区）..."
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend python scripts/seed_data.py
echo "✅ 演示数据填充完成"

echo ""
echo "🔐 申请 Let's Encrypt SSL 证书..."
read -p "请确认域名 $DOMAIN 已解析到本服务器IP (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose -f docker-compose.prod.yml --env-file .env.prod up -d nginx
    sleep 3
    
    docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email admin@$DOMAIN \
        --agree-tos \
        --no-eff-email \
        -d $DOMAIN
    
    echo "✅ SSL 证书申请成功"
    echo ""
    echo "⚙️  更新 Nginx 配置为 HTTPS 模式..."
    sed "s/YOUR_DOMAIN.COM/$DOMAIN/g" nginx/moment.conf.template > nginx/conf.d/moment.conf
    docker compose -f docker-compose.prod.yml --env-file .env.prod restart nginx
else
    echo "⚠️  跳过 SSL 证书申请"
    echo "   你可以稍后手动申请证书，或者直接用 HTTP 访问"
fi

echo ""
echo "🚀 启动所有服务..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

echo ""
echo "======================================"
echo "🎉 初始化完成！"
echo "======================================"
echo ""
echo "📱 访问地址："
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   前端: https://$DOMAIN"
    echo "   API文档: https://$DOMAIN/docs"
else
    echo "   前端: http://$DOMAIN  (或服务器IP)"
    echo "   API文档: http://$DOMAIN/docs"
fi
echo ""
echo "👤 默认管理员账号："
echo "   邮箱: admin@momentcampus.com"
echo "   密码: pass123"
echo ""
echo "📝 常用命令："
echo "   查看日志: docker compose -f docker-compose.prod.yml logs -f"
echo "   停止服务: docker compose -f docker-compose.prod.yml down"
echo "   重启服务: docker compose -f docker-compose.prod.yml restart"
echo "   更新部署: ./deploy.sh"
echo ""

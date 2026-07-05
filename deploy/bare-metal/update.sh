#!/bin/bash
set -e

echo "======================================"
echo "  此刻校园 - 传统部署更新脚本"
echo "======================================"
echo ""

PROJECT_DIR="/opt/moment-campus"

if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本 (sudo bash $0)"
    exit 1
fi

if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ 项目目录不存在：$PROJECT_DIR"
    exit 1
fi

echo "🔄 步骤1：拉取最新代码..."
cd $PROJECT_DIR
if [ -d ".git" ]; then
    git pull
else
    echo "⚠️  不是Git仓库，请手动上传更新代码"
fi
echo ""

echo "🐍 步骤2：更新后端依赖..."
cd $PROJECT_DIR/backend
source .venv/bin/activate
pip install -r requirements.txt
echo ""

echo "🗄️  步骤3：执行数据库迁移..."
alembic upgrade head
echo ""

echo "📦 步骤4：重新构建前端..."
cd $PROJECT_DIR/frontend
npm ci || npm install
npm run build
echo ""

echo "🔄 步骤5：重启服务..."
chown -R moment:moment $PROJECT_DIR
systemctl restart moment-backend
systemctl restart nginx
sleep 2
echo ""

echo "📊 检查服务状态..."
if systemctl is-active --quiet moment-backend; then
    echo "✅ 后端服务运行正常"
else
    echo "❌ 后端服务异常，请检查日志：journalctl -u moment-backend -f"
fi

if systemctl is-active --quiet nginx; then
    echo "✅ Nginx运行正常"
else
    echo "❌ Nginx异常，请检查配置：nginx -t"
fi
echo ""

echo "======================================"
echo "✅ 更新部署完成！"
echo "======================================"
echo ""

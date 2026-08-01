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
cp $PROJECT_DIR/deploy/bare-metal/moment-expire-posts.service /etc/systemd/system/
cp $PROJECT_DIR/deploy/bare-metal/moment-expire-posts.timer /etc/systemd/system/
sed -i "s|/opt/moment-campus|$PROJECT_DIR|g" /etc/systemd/system/moment-expire-posts.service
systemctl daemon-reload
systemctl enable --now moment-expire-posts.timer
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

if systemctl is-active --quiet moment-expire-posts.timer; then
    echo "✅ 自动过期定时器运行正常"
else
    echo "❌ 自动过期定时器异常，请检查：systemctl status moment-expire-posts.timer"
fi
echo ""

echo "======================================"
echo "✅ 更新部署完成！"
echo "======================================"
echo ""

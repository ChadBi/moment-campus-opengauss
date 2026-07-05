#!/bin/bash
set -e

echo "======================================"
echo "  此刻校园 - 传统物理部署初始化脚本"
echo "  (适用于 Ubuntu 22.04 / Debian 12)"
echo "======================================"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本 (sudo su - 或 sudo bash $0)"
    exit 1
fi

PROJECT_DIR="/opt/moment-campus"
SERVICE_USER="moment"
DOMAIN=""

echo ""
echo "⚠️  注意：openGauss 数据库需要你提前安装好！"
echo "   如果还没安装openGauss，请先按文档第3节安装数据库。"
echo ""
read -p "是否继续？(y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

read -p "请输入你的域名 (例如: moment.example.com): " DOMAIN
if [ -z "$DOMAIN" ]; then
    echo "❌ 域名不能为空"
    exit 1
fi

echo ""
echo "📦 步骤1：更新系统并安装基础依赖..."
apt update
apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential libpq-dev \
    nodejs npm \
    nginx \
    certbot python3-certbot-nginx \
    git curl wget vim

echo "✅ 基础依赖安装完成"
echo ""

echo "📦 步骤2：创建运行用户..."
id -u $SERVICE_USER &>/dev/null || useradd -r -s /bin/bash -m -d /home/$SERVICE_USER $SERVICE_USER
echo "✅ 用户 $SERVICE_USER 创建完成"
echo ""

echo "📂 步骤3：检查项目目录..."
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ 项目目录不存在：$PROJECT_DIR"
    echo "   请先将项目代码上传到 $PROJECT_DIR"
    echo "   可以使用 Git 克隆或 scp 上传"
    echo ""
    echo "   Git 方式示例："
    echo "   cd /opt && git clone 你的仓库地址 moment-campus"
    exit 1
fi
echo "✅ 项目目录存在"
echo ""

echo "🐍 步骤4：配置 Python 后端环境..."
cd $PROJECT_DIR/backend

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Python 依赖安装完成"

mkdir -p uploads
chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR
echo ""

echo "⚙️  步骤5：配置后端环境变量..."
if [ ! -f ".env.prod" ]; then
    cp $PROJECT_DIR/deploy/bare-metal/.env.prod.example .env.prod
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/change-this-to-a-strong-random-secret-key-in-production-please-use-openssl/$SECRET_KEY/g" .env.prod
    sed -i "s/YOUR_DOMAIN.COM/$DOMAIN/g" .env.prod
    echo "✅ 已生成 .env.prod，SECRET_KEY 已自动设置"
    echo ""
    echo "⚠️  重要：请检查并修改 .env.prod 中的数据库密码！"
    echo "   当前默认密码是 Gaussdb@123，如果你的数据库密码不同，请修改"
fi
echo ""

echo "🗄️  步骤6：初始化数据库..."
read -p "数据库是否已启动并创建了 moment_campus 数据库？(y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    source .venv/bin/activate
    echo "   执行 Alembic 数据库迁移..."
    alembic upgrade head || echo "⚠️  迁移失败，如果是首次部署，seed_data.py会自动建表"
    echo ""
    echo "   填充江南大学演示数据..."
    python scripts/seed_data.py
    echo "✅ 数据库初始化完成"
else
    echo "⚠️  跳过数据库初始化，请先安装并启动openGauss后手动执行："
    echo "   cd $PROJECT_DIR/backend"
    echo "   source .venv/bin/activate"
    echo "   alembic upgrade head"
    echo "   python scripts/seed_data.py"
fi
echo ""

echo "📦 步骤7：构建前端..."
cd $PROJECT_DIR/frontend

if [ ! -d "node_modules" ]; then
    npm ci || npm install
fi
echo "   执行生产构建..."
npm run build
echo "✅ 前端构建完成 (dist/ 目录)"
echo ""

echo "⚙️  步骤8：配置 systemd 服务..."
cp $PROJECT_DIR/deploy/bare-metal/moment-backend.service /etc/systemd/system/
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR/backend|g" /etc/systemd/system/moment-backend.service
sed -i "s|Environment=\"PATH=.*|Environment=\"PATH=$PROJECT_DIR/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin\"|g" /etc/systemd/system/moment-backend.service
sed -i "s|ExecStart=.*|ExecStart=$PROJECT_DIR/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4|g" /etc/systemd/system/moment-backend.service
systemctl daemon-reload
systemctl enable moment-backend
echo "✅ systemd 服务配置完成"
echo ""

echo "🌐 步骤9：配置 Nginx（HTTP模式，用于申请证书）..."
mkdir -p /var/www/certbot
cp $PROJECT_DIR/deploy/bare-metal/nginx-moment-http.conf /etc/nginx/sites-available/moment
sed -i "s/YOUR_DOMAIN.COM/$DOMAIN/g" /etc/nginx/sites-available/moment
ln -sf /etc/nginx/sites-available/moment /etc/nginx/sites-enabled/moment
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
echo "✅ Nginx HTTP配置完成"
echo ""

echo "🔐 步骤10：启动后端服务..."
chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR
systemctl start moment-backend
sleep 3
if systemctl is-active --quiet moment-backend; then
    echo "✅ 后端服务启动成功"
else
    echo "❌ 后端服务启动失败，请检查日志："
    echo "   journalctl -u moment-backend -f"
fi
echo ""

echo "🔐 步骤11：申请 SSL 证书..."
read -p "请确认域名 $DOMAIN 已解析到本服务器IP (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
    echo "✅ SSL 证书申请成功，Nginx已自动配置HTTPS"
else
    echo "⚠️  跳过证书申请"
    echo "   你可以稍后手动执行："
    echo "   certbot --nginx -d $DOMAIN"
fi
echo ""

echo "🔄 步骤12：重启所有服务..."
systemctl restart moment-backend
systemctl restart nginx
echo ""

echo "======================================"
echo "🎉 传统部署初始化完成！"
echo "======================================"
echo ""
echo "📱 访问地址："
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   前端: https://$DOMAIN"
    echo "   API文档: https://$DOMAIN/docs"
else
    echo "   前端: http://$DOMAIN (或服务器IP)"
    echo "   API文档: http://$DOMAIN/docs"
fi
echo ""
echo "👤 默认管理员账号："
echo "   邮箱: admin@momentcampus.com"
echo "   密码: pass123"
echo ""
echo "📝 常用运维命令："
echo "   查看后端日志: journalctl -u moment-backend -f"
echo "   重启后端: systemctl restart moment-backend"
echo "   重启Nginx: systemctl restart nginx"
echo "   查看服务状态: systemctl status moment-backend nginx"
echo ""

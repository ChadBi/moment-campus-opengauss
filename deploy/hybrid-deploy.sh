#!/bin/bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/moment-campus}"
DOMAIN="${DOMAIN:-campus.chaina1.com}"
PUBLIC_IP="${PUBLIC_IP:-123.60.101.165}"
SERVICE_USER="${SERVICE_USER:-moment}"

cd "$PROJECT_DIR"

if [ ! -f deploy/.env.prod ]; then
    echo "Missing deploy/.env.prod"
    exit 1
fi

set -a
. deploy/.env.prod
set +a

mkdir -p backend/uploads frontend/dist /var/www/certbot

cat > backend/.env.prod <<EOF
APP_NAME=此刻校园
APP_ENV=production
DEBUG=False
API_V1_PREFIX=/api/v1
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD_ENCODED}@127.0.0.1:5432/${DB_NAME}
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256
UPLOAD_DIR=${PROJECT_DIR}/backend/uploads
MAX_UPLOAD_SIZE=5242880
CORS_ORIGINS='["https://${DOMAIN}","http://${DOMAIN}","http://${PUBLIC_IP}"]'
LOG_LEVEL=INFO
EOF
cp backend/.env.prod backend/.env.opengauss
chmod 600 backend/.env.prod backend/.env.opengauss

id -u "$SERVICE_USER" >/dev/null 2>&1 || useradd -r -s /bin/bash -m -d "/home/$SERVICE_USER" "$SERVICE_USER"

cd "$PROJECT_DIR/backend"
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
. .venv/bin/activate
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple >/dev/null
pip install -r requirements.txt
set -a
. ./.env.prod
set +a

python - <<'PY'
from app.config import settings

print("Backend config OK:", settings.DATABASE_URL.rsplit("@", 1)[1])
print("CORS origins:", len(settings.CORS_ORIGINS))
PY

alembic upgrade head
python scripts/seed_data.py

cat > /etc/systemd/system/moment-backend.service <<EOF
[Unit]
Description=Moment Campus Backend (FastAPI)
After=network.target docker.service

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}/backend
Environment="PATH=${PROJECT_DIR}/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=${PROJECT_DIR}/backend/.env.prod
ExecStart=${PROJECT_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=moment-backend
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

cp "$PROJECT_DIR/deploy/bare-metal/moment-expire-posts.service" /etc/systemd/system/
cp "$PROJECT_DIR/deploy/bare-metal/moment-expire-posts.timer" /etc/systemd/system/
cp "$PROJECT_DIR/deploy/bare-metal/moment-location-summaries.service" /etc/systemd/system/
cp "$PROJECT_DIR/deploy/bare-metal/moment-location-summaries.timer" /etc/systemd/system/
sed -i "s|User=.*|User=${SERVICE_USER}|g; s|Group=.*|Group=${SERVICE_USER}|g; s|/opt/moment-campus|${PROJECT_DIR}|g" /etc/systemd/system/moment-expire-posts.service
sed -i "s|User=.*|User=${SERVICE_USER}|g; s|Group=.*|Group=${SERVICE_USER}|g; s|/opt/moment-campus|${PROJECT_DIR}|g" /etc/systemd/system/moment-location-summaries.service

if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ] && [ -f "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" ]; then
cat > /etc/nginx/sites-available/moment <<EOF
server {
    listen 80;
    server_name ${DOMAIN} ${PUBLIC_IP};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root ${PROJECT_DIR}/frontend/dist;
    index index.html;
    client_max_body_size 10M;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript application/json image/svg+xml;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /assets/ {
        try_files \$uri =404;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        access_log off;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ^~ /uploads/ {
        alias ${PROJECT_DIR}/backend/uploads/;
    }

    location ~* \.(?:js|css|png|jpg|jpeg|gif|ico|svg|webp|avif|woff|woff2|ttf|eot)$ {
        try_files \$uri =404;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        access_log off;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate" always;
    }
}
EOF
else
cat > /etc/nginx/sites-available/moment <<EOF
server {
    listen 80;
    server_name ${DOMAIN} ${PUBLIC_IP};

    root ${PROJECT_DIR}/frontend/dist;
    index index.html;
    client_max_body_size 10M;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript application/json image/svg+xml;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /assets/ {
        try_files \$uri =404;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        access_log off;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ^~ /uploads/ {
        alias ${PROJECT_DIR}/backend/uploads/;
    }

    location ~* \.(?:js|css|png|jpg|jpeg|gif|ico|svg|webp|avif|woff|woff2|ttf|eot)$ {
        try_files \$uri =404;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        access_log off;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate" always;
    }
}
EOF
fi

ln -sf /etc/nginx/sites-available/moment /etc/nginx/sites-enabled/moment
rm -f /etc/nginx/sites-enabled/default

chown -R "$SERVICE_USER:$SERVICE_USER" "$PROJECT_DIR"
systemctl daemon-reload
systemctl enable moment-backend
systemctl enable --now moment-expire-posts.timer
systemctl enable --now moment-location-summaries.timer
systemctl restart moment-backend
nginx -t
systemctl restart nginx

echo "Hybrid deployment configured."

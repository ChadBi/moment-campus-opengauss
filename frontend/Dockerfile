FROM node:20-alpine AS builder

WORKDIR /app

# P0-001: 声明 VITE_API_BASE_URL 构建参数，让 docker-compose.prod.yml 传入的同源 /api/v1 生效
# 缺失此声明会导致构建参数被静默丢弃，前端回退到 http://localhost:8000/api/v1，生产部署即坏
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

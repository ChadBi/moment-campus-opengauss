#!/bin/bash
# ============================================================
# 脚本名称：install_crontab.sh
# 用途：将 crontab 定时任务配置安装到系统 crontab
# 依据：docs/27_数据库物理模型设计.md 第 8.2 节
# 创建时间：2026-06-29
# 使用方法：
#   1. 修改下方环境变量为本机实际路径
#   2. chmod +x install_crontab.sh
#   3. sudo ./install_crontab.sh
# 说明：
#   1. 本脚本在 Linux 环境下运行（openGauss 容器宿主机或容器内）
#   2. 需 root 权限安装到系统 crontab
#   3. 安装前会备份现有 crontab 到 crontab.backup.{timestamp}
# ============================================================

# ===== 环境变量配置（请根据实际环境修改）=====
# psql 可执行文件路径（openGauss 客户端）
PSQL_PATH="${PSQL_PATH:-/usr/local/bin/psql}"

# 数据库连接信息
DB_USER="${DB_USER:-omm}"
DB_NAME="${DB_NAME:-moment_campus}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"

# 日志目录
LOG_DIR="${LOG_DIR:-/var/log/momentcampus/cron}"

# crontab 文件路径（与本脚本同目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRONTAB_FILE="${SCRIPT_DIR}/crontab"

# 备份目录
BACKUP_DIR="${SCRIPT_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ===== 颜色输出 =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ===== 检查前置条件 =====
info "开始安装此刻校园定时任务..."

# 检查 psql 是否存在
if [ ! -x "${PSQL_PATH}" ]; then
    warn "psql 未找到：${PSQL_PATH}"
    warn "请通过环境变量 PSQL_PATH 指定，例如："
    warn "  export PSQL_PATH=/opt/openGauss/bin/psql"
    warn "  或修改本脚本中的 PSQL_PATH 变量"
    # 不退出，允许用户先安装
fi

# 检查 crontab 命令是否可用
if ! command -v crontab >/dev/null 2>&1; then
    error "crontab 命令不可用，请先安装 cron 服务"
    exit 1
fi

# 检查 crontab 配置文件
if [ ! -f "${CRONTAB_FILE}" ]; then
    error "crontab 配置文件不存在：${CRONTAB_FILE}"
    exit 1
fi

# ===== 创建日志目录 =====
info "创建日志目录：${LOG_DIR}"
mkdir -p "${LOG_DIR}"
chmod 755 "${LOG_DIR}"

# ===== 创建备份目录 =====
info "创建备份目录：${BACKUP_DIR}"
mkdir -p "${BACKUP_DIR}"

# ===== 备份现有 crontab =====
if crontab -l >/dev/null 2>&1; then
    BACKUP_FILE="${BACKUP_DIR}/crontab.backup.${TIMESTAMP}"
    info "备份现有 crontab 到：${BACKUP_FILE}"
    crontab -l > "${BACKUP_FILE}"
    echo "" >> "${BACKUP_FILE}"
    echo "# ===== 以下为本次安装的时刻校园定时任务 =====" >> "${BACKUP_FILE}"
else
    info "当前无 crontab 配置，将创建新配置"
fi

# ===== 生成临时 crontab 文件（带环境变量替换）=====
TEMP_CRONTAB="${BACKUP_DIR}/crontab.merged.${TIMESTAMP}"

# 1. 保留现有 crontab（若存在）
if crontab -l >/dev/null 2>&1; then
    crontab -l > "${TEMP_CRONTAB}"
    echo "" >> "${TEMP_CRONTAB}"
fi

# 2. 追加环境变量定义
cat >> "${TEMP_CRONTAB}" << EOF
# ===== 此刻校园 openGauss 定时任务（${TIMESTAMP} 安装）=====
PSQL_PATH=${PSQL_PATH}
DB_USER=${DB_USER}
DB_NAME=${DB_NAME}
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
LOG_DIR=${LOG_DIR}

EOF

# 3. 追加 crontab 文件内容（过滤注释行和空行，保留有效任务行）
grep -v '^#' "${CRONTAB_FILE}" | grep -v '^\s*$' | grep -v '^\s*PSQL_PATH' | grep -v '^\s*DB_' | grep -v '^\s*LOG_DIR' >> "${TEMP_CRONTAB}"

# ===== 安装新 crontab =====
info "安装新 crontab 配置..."
crontab "${TEMP_CRONTAB}"

if [ $? -eq 0 ]; then
    info "crontab 安装成功！"
else
    error "crontab 安装失败"
    exit 1
fi

# ===== 验证安装结果 =====
echo ""
info "===== 当前 crontab 配置 ====="
crontab -l
echo ""

# ===== 检查 cron 服务状态 =====
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet cron 2>/dev/null || systemctl is-active --quiet crond 2>/dev/null; then
        info "cron 服务运行中"
    else
        warn "cron 服务未运行，请手动启动："
        warn "  sudo systemctl start cron   # Debian/Ubuntu"
        warn "  sudo systemctl start crond  # CentOS/RHEL"
        warn "  sudo systemctl enable cron  # 设置开机自启"
    fi
fi

# ===== 测试数据库连接 =====
info "测试数据库连接..."
if [ -x "${PSQL_PATH}" ]; then
    "${PSQL_PATH}" -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 'crontab_install_test' AS status, NOW() AS tested_at;" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        info "数据库连接测试成功"
    else
        warn "数据库连接测试失败，请检查："
        warn "  1. openGauss 服务是否运行"
        warn "  2. ~/.pgpass 或环境变量 PGPASSWORD 是否配置"
        warn "  3. 数据库 ${DB_NAME} 是否存在"
        warn "  4. 用户 ${DB_USER} 是否有访问权限"
    fi
fi

echo ""
info "===== 安装完成 ====="
info "定时任务已安装，日志目录：${LOG_DIR}"
info "备份文件：${BACKUP_DIR}/"
info ""
info "常用命令："
info "  查看任务：    crontab -l"
info "  编辑任务：    crontab -e"
info "  删除所有任务：crontab -r"
info "  查看日志：    tail -f ${LOG_DIR}/job*.log"
info "  查看cron状态：systemctl status cron"
info ""
info "卸载方法："
info "  恢复备份：    crontab ${BACKUP_DIR}/crontab.backup.${TIMESTAMP}"

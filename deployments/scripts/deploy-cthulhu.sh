#!/bin/bash

# Angular 项目部署脚本
# 使用方法: ./deploy-angular.sh

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "命令 $1 未找到，请先安装"
        exit 1
    fi
}

# 配置变量 - 请根据实际情况修改
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # 脚本所在目录
PROJECT_DIR="$SCRIPT_DIR/../../app/projects/cthulhu"        # 从脚本目录计算的相对路径
PROJECT_NAME="cthulhu"                                      # Angular 项目名称
REMOTE_USER="machine"                                       # 远程服务器用户名
REMOTE_HOST="192.168.31.72"                                # 远程服务器地址
REMOTE_PORT="22"                                           # SSH 端口，默认 22
REMOTE_BASE_DIR="/home/machine/data_volume/nginx/html"     # 远程基础目录（使用绝对路径）

# 检查必要命令
check_command "ng"
check_command "ssh"
check_command "scp"

# 解析完整项目路径
FULL_PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
log_info "项目目录: $FULL_PROJECT_DIR"

# 切换到项目目录
cd "$FULL_PROJECT_DIR" || {
    log_error "无法切换到项目目录: $FULL_PROJECT_DIR"
    exit 1
}

log_info "开始构建 Angular 应用..."

# 执行构建命令
if ng build --configuration production; then
    log_info "Angular 应用构建成功"
else
    log_error "Angular 应用构建失败"
    exit 1
fi

# 构建输出目录路径 - 修正路径格式
BUILD_PATH="$FULL_PROJECT_DIR/dist/$PROJECT_NAME/browser"

if [ ! -d "$BUILD_PATH" ]; then
    log_error "构建输出目录不存在: $BUILD_PATH"
    log_info "dist 目录结构:"
    find "$FULL_PROJECT_DIR/dist" -type d -print 2>/dev/null | sed 's/^/  /'
    log_info "尝试自动检测构建目录..."

    # 自动检测 browser 目录
    DETECTED_BROWSER_DIR=$(find "$FULL_PROJECT_DIR/dist" -name "browser" -type d 2>/dev/null | head -1)
    if [ -n "$DETECTED_BROWSER_DIR" ] && [ -d "$DETECTED_BROWSER_DIR" ]; then
        BUILD_PATH="$DETECTED_BROWSER_DIR"
        log_info "自动检测到 browser 目录: $BUILD_PATH"
    else
        log_error "无法找到 browser 目录，请手动检查构建输出"
        exit 1
    fi
fi

log_info "构建输出目录: $BUILD_PATH"

# 创建临时目录用于打包
TEMP_DIR=$(mktemp -d)
log_info "创建临时目录: $TEMP_DIR"

# 复制 browser 目录内容到临时目录
cp -r "$BUILD_PATH" "$TEMP_DIR/"
log_info "复制构建文件到临时目录"

# 只询问一次密码
read -s -p "请输入远程服务器密码: " SSH_PASSWORD
echo

# 设置 SSH 认证
export SSHPASS="$SSH_PASSWORD"

# 检查是否安装了 sshpass
if ! command -v sshpass &> /dev/null; then
    log_error "请先安装 sshpass: sudo apt-get install sshpass"
    exit 1
fi

# 部署到远程服务器
log_info "开始部署到远程服务器 $REMOTE_HOST..."

# 第一步：删除远程的 browser 目录
log_info "删除远程现有的 browser 目录..."
if sshpass -e ssh -p "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST" "rm -rf $REMOTE_BASE_DIR/browser"; then
    log_info "远程 browser 目录删除成功"
else
    log_warn "删除远程 browser 目录时遇到问题，继续执行..."
fi

# 第二步：确保远程目录存在
log_info "确保远程目录存在..."
sshpass -e ssh -p "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST" "mkdir -p $REMOTE_BASE_DIR"

# 第三步：上传 browser 目录内容
log_info "上传 browser 目录内容..."
if sshpass -e scp -r -P "$REMOTE_PORT" "$TEMP_DIR/browser" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE_DIR/"; then
    log_info "browser 目录上传成功"
else
    log_error "browser 目录上传失败"
    # 清理临时目录
    rm -rf "$TEMP_DIR"
    exit 1
fi

# 第四步：验证部署
log_info "验证远程部署..."
REMOTE_RESULT=$(sshpass -e ssh -p "$REMOTE_PORT" "$REMOTE_USER@$REMOTE_HOST" "ls -la $REMOTE_BASE_DIR/browser/ | head -10")

if [ -n "$REMOTE_RESULT" ]; then
    log_info "远程 browser 目录内容:"
    echo "$REMOTE_RESULT"
    log_info "部署完成！Angular 应用已成功部署到 $REMOTE_HOST:$REMOTE_BASE_DIR/browser"
else
    log_error "部署验证失败，请检查远程目录"
fi

# 清理临时目录
log_info "清理临时目录..."
rm -rf "$TEMP_DIR"

# 清除密码变量
unset SSHPASS
unset SSH_PASSWORD

log_info "所有操作完成！"
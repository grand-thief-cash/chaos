echo "Current workspace: ${WORKSPACE}"
echo "Current branch: ${branch}"

# 设置 Go 环境
export PATH=/var/go/bin:$PATH
echo "Go 版本:"
go version

echo "=== 获取当前版本 ==="
VERSION=$(awk '/^# VERSION/{getline; print; exit}' app/projects/cronjob/CHANGELOG | tr -d '\r')
VERSION=$(echo "$VERSION" | sed 's/^v//')  # 清理版本号

echo "当前版本: $VERSION"

echo "=== 检查是否已存在该版本的 Docker 镜像 ==="
if docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "cronjob:$VERSION"; then
    echo "✅ 版本 $VERSION 的 Docker 镜像已存在，跳过构建"
    echo "现有镜像信息:"
    docker images | grep "cronjob.*$VERSION"

    # 检查是否有运行中的容器使用旧版本
    RUNNING_IMAGE=$(docker inspect cronjob-app --format '{{.Config.Image}}' 2>/dev/null || echo "")
    if [ "$RUNNING_IMAGE" = "cronjob:$VERSION" ]; then
        echo "✅ 当前运行中的容器已经是最新版本 $VERSION"
        echo "=== 跳过构建和部署流程 ==="
        exit 0
    else
        echo "🔄 运行中的容器版本不同，继续部署流程..."
    fi
else
    echo "🔄 开始构建版本 $VERSION 的 Docker 镜像"
fi

echo "=== 进入 Go 代码目录 ==="
cd app/projects/cronjob

echo "=== 详细依赖处理 ==="
go mod tidy -v
go mod verify

echo "=== 检查是否已存在该版本的可执行文件 ==="
BUILD_OUTPUT="cronjob-app-v${VERSION}"

if [ -f "$BUILD_OUTPUT" ]; then
    echo "✅ 版本 $VERSION 的可执行文件已存在，跳过构建"
    echo "文件信息:"
    ls -la "$BUILD_OUTPUT"
else
    echo "🔄 开始构建版本 $VERSION"

    # 清理旧版本的可执行文件
    echo "清理旧版本文件..."
    find . -name "cronjob-app*" -type f ! -name "$BUILD_OUTPUT" -delete 2>/dev/null || true

    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -v -ldflags="-X 'main.Version=$VERSION'" -o "$BUILD_OUTPUT" ./cmd

    echo "=== 检查构建是否成功 ==="
    if [ -f "$BUILD_OUTPUT" ]; then
        echo "✅ Go 应用构建成功: $BUILD_OUTPUT"
        ls -la "$BUILD_OUTPUT"

        # 更新软链接指向最新版本
        ln -sf "$BUILD_OUTPUT" cronjob-app
        echo "✅ 更新软链接: cronjob-app -> $BUILD_OUTPUT"
    else
        echo "❌ Go 应用构建失败"
        exit 1
    fi
fi

cd ${WORKSPACE}

echo "=== 清理旧版本的 Docker 镜像 ==="
# 获取所有 cronjob 镜像，排除当前版本
OLD_IMAGES=$(docker images --filter "reference=cronjob*" --format "{{.Repository}}:{{.Tag}}" | grep -v "cronjob:$VERSION" || true)

if [ -n "$OLD_IMAGES" ]; then
    echo "找到以下旧版本镜像，准备清理:"
    echo "$OLD_IMAGES"

    # 删除旧版本镜像
    for image in $OLD_IMAGES; do
        echo "删除镜像: $image"
        docker rmi "$image" 2>/dev/null || echo "无法删除镜像 $image，可能正在被使用"
    done
else
    echo "没有找到需要清理的旧版本镜像"
fi

echo "=== 准备 Docker 构建上下文 ==="
# 创建临时构建目录
mkdir -p docker_build_context
cp "app/projects/cronjob/cronjob-app-v${VERSION}" "docker_build_context/cronjob-app-v${VERSION}"
cp "app/projects/cronjob/migrations" "docker_build_context/migrations"
# 复制 Dockerfile 到构建上下文
cp "deploy/docker/dockerfile/Dockerfile-cronjob" "docker_build_context/Dockerfile"

echo "=== Docker 构建上下文内容 ==="
ls -la docker_build_context/

echo "=== 构建 Docker 镜像 ==="
cd docker_build_context

docker build \
    --network=host \
    --build-arg VERSION=$VERSION \
    --build-arg HTTP_PROXY=http://192.168.31.170:7890 \
    --build-arg HTTPS_PROXY=http://192.168.31.170:7890 \
    -t cronjob:$VERSION .

BUILD_RESULT=$?
cd ${WORKSPACE}

if [ $BUILD_RESULT -eq 0 ] && docker images | grep -q "cronjob.*$VERSION"; then
    echo "✅ Docker 镜像构建成功: cronjob:$VERSION"
else
    echo "❌ Docker 镜像构建失败"
    exit 1
fi

echo "=== 清理临时文件 ==="
rm -rf docker_build_context

echo "=== 开始部署应用 ==="
# 安装 Docker Compose（如果尚未安装）
echo "=== 检查并安装 Docker Compose ==="

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Docker Compose 未安装，开始安装..."
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -x http://192.168.31.170:7890 -SL "https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    echo "✅ Docker Compose 安装完成"
else
    echo "✅ Docker Compose 已安装"
fi

# 设置环境变量供 docker-compose 使用
export VERSION=$VERSION

# 停止并删除旧容器
echo "停止旧容器..."
docker stop cronjob-app 2>/dev/null || echo "没有运行中的 cronjob-app 容器"
docker rm cronjob-app 2>/dev/null || echo "没有可删除的 cronjob-app 容器"

# 使用 docker-compose 启动新容器
echo "启动新容器..."
docker compose -f deploy/docker/docker-compose/cronjob.yaml up -d

# 检查服务状态
echo "检查服务状态..."
sleep 10
docker ps | grep cronjob-app || echo "容器可能启动失败"

echo "=== 最终镜像状态 ==="
docker images | grep "cronjob"

echo "=== 构建和部署流程完成 ==="
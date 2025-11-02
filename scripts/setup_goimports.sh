#!/bin/bash

# 确保 goimports 已经安装
go install golang.org/x/tools/cmd/goimports@latest

# GOPATH 默认 ~/go，如果没设置用 go env 获取
GOBIN=$(go env GOPATH)/bin

# 写入到 ~/.bashrc
if ! grep -q "$GOBIN" ~/.bashrc; then
    echo "export PATH=\$PATH:$GOBIN" >> ~/.bashrc
    echo "已将 $GOBIN 添加到 PATH，执行 'source ~/.bashrc' 生效"
else
    echo "$GOBIN 已存在于 PATH"
fi

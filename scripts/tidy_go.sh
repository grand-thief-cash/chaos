#!/bin/bash

# working directory is the parent directory of this script
work_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Working directory is $work_dir"

# 定义一个路径数组
paths=(
    "app/infra/go/common"
    "app/infra/go/application"
    "app/poc/infra/go/application"
    "app/poc/infra/go/client"
    "app/poc/projects/cronjob"
    "app/projects/cronjob"
    "app/projects/phoenixA"

)

# 遍历路径数组并执行 go mod tidy
for path in "${paths[@]}"; do
    full_path="$work_dir/$path"
    if [ -d "$full_path" ]; then
        echo "Running 'go mod tidy && go mod vendor' in $full_path"
        (cd "$full_path" && go mod tidy && go mod vendor)
    else
        echo "Directory $full_path does not exist, skipping."
    fi
done
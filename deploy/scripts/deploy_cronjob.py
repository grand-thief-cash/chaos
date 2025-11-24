#!/usr/bin/env python3
import os
import paramiko
import subprocess
import sys
from pathlib import Path
import shutil
import time


#########################################
# --------- 配置区域 ----------
#########################################

GO_PROJECT_PATH = "../../app/projects/cronjob"
REMOTE_DEPLOY_PATH = "/home/machine/docker_deploy/cronjob"
REMOTE_HOST = "192.168.31.72"
REMOTE_USER = "machine"
REMOTE_PASS = "123456"

DOCKERFILE_PATH = "../docker/dockerfile/Dockerfile-cronjob"
DOCKER_COMPOSE_FILE = "cronjob.yaml"
DOCKER_COMPOSE_FOLDER = "../docker/docker-compose"

FORCE_GO_BUILD = False
FORCE_DOCKER_COMPOSE_BUILD = True
FORCE_DOCKER_BUILD = True
SERVICE_NAME = "cronjob"

VPN = "192.168.31.169:7890"


#########################################
# 工具方法
#########################################

def read_version():
    changelog = Path(GO_PROJECT_PATH) / "CHANGELOG"
    version = None
    with open(changelog, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("v"):
                version = line
                break
    if not version:
        print("❌ 未找到版本号")
        sys.exit(1)

    print(f"✔ 项目版本号: {version}")
    return version


def local_go_build(version):

    dist_path = Path(GO_PROJECT_PATH).resolve() / "dist"
    dist_path.mkdir(exist_ok=True)

    build_name = f"{SERVICE_NAME}-{version}"
    output_file = dist_path / build_name

    if output_file.exists() and not FORCE_GO_BUILD:
        print(f"✔ dist/{build_name} 已存在，跳过 go build")
        return output_file

    print("🔨 执行 go build ...")

    cmd = ["go", "build", "-o", str(output_file), "./cmd"]

    # 显式传递 PATH，确保 Python venv 也能找到 go
    env = os.environ.copy()
    env["GOTOOLCHAIN"] = "local"   # ⭐ 这里！
    env["PATH"] = "/usr/local/go/bin:" + env["PATH"]

    subprocess.check_call(cmd, cwd=GO_PROJECT_PATH, env=env)

    print(f"✔ go build 完成: {output_file}")
    return output_file


def ssh_connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS)
    return ssh
def sftp_upload(ssh, local_path, remote_path):
    sftp = ssh.open_sftp()

    local_path = str(local_path)
    remote_path = str(remote_path).replace("\\", "/")

    if os.path.isdir(local_path):
        # 创建 remote 根目录
        try:
            sftp.mkdir(remote_path)
        except IOError:
            pass

        # 递归上传目录
        for root, dirs, files in os.walk(local_path):
            rel = os.path.relpath(root, local_path)
            rel = "" if rel == "." else rel

            remote_dir = os.path.join(remote_path, rel).replace("\\", "/")

            # 创建目录
            try:
                sftp.mkdir(remote_dir)
            except IOError:
                pass

            # 上传文件
            for filename in files:
                local_file = os.path.join(root, filename)
                remote_file = os.path.join(remote_dir, filename).replace("\\", "/")
                sftp.put(local_file, remote_file)
    else:
        # 单文件上传
        sftp.put(local_path, remote_path)

    sftp.close()

def rsync_upload(local_path, remote_path):
    cmd = f'rsync -azP {local_path} {REMOTE_USER}@{REMOTE_HOST}:{remote_path}'
    print(f"⬆️ 上传文件: {cmd}")
    subprocess.check_call(cmd, shell=True)


def create_temp_compose(version):
    """
    自动替换 compose 文件中的 image tag
    image: cronjob:xxxx → cronjob:v0.12.6
    """
    tmp_compose = os.path.join(Path(GO_PROJECT_PATH).resolve(), "dist", f"cronjob-{version}.yaml")
    # 如果文件已存在且不强制重新生成，则跳过
    if os.path.exists(tmp_compose) and not FORCE_DOCKER_COMPOSE_BUILD:
        print(f"✓ compose 文件已存在，跳过生成: {tmp_compose}")
        return tmp_compose

    docker_compose_template = os.path.join(DOCKER_COMPOSE_FOLDER, DOCKER_COMPOSE_FILE)
    with open(docker_compose_template, "r") as f:
        content = f.read()

    new_content = []
    for line in content.splitlines():
        if "image:" in line and SERVICE_NAME in line:
            new_content.append(f"    image: {SERVICE_NAME}:{version}")
        else:
            new_content.append(line)
    # tmp_compose = os.path.join(DOCKER_COMPOSE_FOLDER, DOCKER_COMPOSE_FILE)
    with open(tmp_compose, "w") as f:
        f.write("\n".join(new_content))

    print(f"✔ compose 文件版本号替换完成: {tmp_compose}")
    return tmp_compose


def upload_files(build_file, compose_file):
    print("⬆️ 上传构建产物和 docker 文件...")

    ssh = ssh_connect()

    sftp_upload(ssh, build_file, f"{REMOTE_DEPLOY_PATH}/{SERVICE_NAME}")
    sftp_upload(ssh, DOCKERFILE_PATH, f"{REMOTE_DEPLOY_PATH}/Dockerfile")
    sftp_upload(ssh, compose_file, f"{REMOTE_DEPLOY_PATH}/docker-compose.yaml")
    sftp_upload(ssh, f"{GO_PROJECT_PATH}/migrations", f"{REMOTE_DEPLOY_PATH}/migrations")

    ssh.close()


def remote_exec(ssh, cmd):
    print(f"🚀 执行远程命令: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if err:
        print("⚠️ 错误输出:", err)
    return out


def get_remote_version(ssh):
    cmd = f"docker ps --filter 'name={SERVICE_NAME}' --format '{{{{.Image}}}}'"
    result = remote_exec(ssh, cmd).strip()
    if not result:
        return None

    if ":" in result:
        return result.split(":")[1]
    return None


def stop_old_container(ssh):
    """
    NEW: 启动前先停止旧容器
    """
    print("🔍 检查旧容器 ...")
    cmd = f"docker ps --filter 'name={SERVICE_NAME}' --format '{{{{.ID}}}}'"
    cid = remote_exec(ssh, cmd).strip()

    if cid:
        print(f"🛑 停止旧容器: {cid}")
        remote_exec(ssh, f"docker stop {SERVICE_NAME}")
        remote_exec(ssh, f"docker rm {SERVICE_NAME}")
    else:
        print("✔ 没有旧容器")


def build_remote_image(ssh, version):
    print("🔨 开始构建 docker 镜像...")
    # 使用 plain 格式输出，显示所有细节
    cmd = f"cd {REMOTE_DEPLOY_PATH} && docker build --network=host --progress=plain --build-arg HTTP_PROXY=http://{VPN} --build-arg HTTPS_PROXY=http://{VPN} -t {SERVICE_NAME}:{version} ."

    stdin, stdout, stderr = ssh.exec_command(cmd)

    print("=== Docker Build 详细输出 ===")
    while True:
        line = stdout.readline()
        if not line:
            break
        print(f"BUILD: {line.strip()}")

    print(f"✔ 镜像构建完成: {SERVICE_NAME}:{version}")


def docker_compose_up(ssh):
    cmd = f"cd {REMOTE_DEPLOY_PATH} && docker compose -f docker-compose.yaml up -d"
    remote_exec(ssh, cmd)
    print("✔ docker compose 启动完成")


def clean_old_images(ssh, version):
    cmd = f"docker images {SERVICE_NAME} --format '{{{{.Tag}}}}'"
    tags = remote_exec(ssh, cmd).splitlines()

    for tag in tags:
        if tag and tag != version:
            print(f"🧹 清理旧镜像: {SERVICE_NAME}:{tag}")
            remote_exec(ssh, f"docker rmi {SERVICE_NAME}:{tag}")
# 返回清理函数
def cleanup(tmp_dir):
    import shutil
    shutil.rmtree(tmp_dir)
    print(f"✔ 临时目录已清理: {tmp_dir}")
def get_container_status(ssh):
    """
    获取容器状态：可能返回：
    - Up x minutes
    - Restarting (xxx)
    - Exited (xxx)
    - ""
    """
    cmd = f"docker ps -a --filter 'name={SERVICE_NAME}' --format '{{{{.Status}}}}'"
    status = remote_exec(ssh, cmd).strip()
    return status
def print_container_logs(ssh, tail=200):
    print("📜 获取容器日志...")
    cmd = f"docker logs --tail {tail} {SERVICE_NAME}"
    logs = remote_exec(ssh, cmd)
    print("======= Docker Logs =======")
    print(logs)
    print("======= END Logs =======")

def wait_container_status(ssh, timeout=60):
    """
    等待容器进入 Up 状态，否则打印日志并退出
    """
    print("⏳ 等待容器启动...")

    for i in range(timeout):
        status = get_container_status(ssh)
        if not status:
            print("⚠️ 容器未找到，1秒后重试...")
            time.sleep(1)
            continue

        print(f"🔍 当前容器状态: {status}")

        # 成功
        if status.startswith("Up"):
            print("🎉 服务已启动成功")
            return True

        # 重启错误
        if "Restarting" in status:
            print("❌ 服务正在 Restarting，可能启动失败")
            print_container_logs(ssh)
            sys.exit(1)

        # 退出错误
        if "Exited" in status:
            print("❌ 服务启动失败（Exited）")
            print_container_logs(ssh)
            sys.exit(1)

        time.sleep(1)

    print("❌ 等待容器启动超时！")
    print_container_logs(ssh)
    sys.exit(1)

#########################################
# --------------- 主流程 ----------------
#########################################

def main():
    version = read_version()
    build_file = local_go_build(version)
    #
    # # NEW: 创建带版本号的 compose
    compose_file = create_temp_compose(version)
    #
    upload_files(build_file, compose_file)

    # 清理临时目录
    # cleanup(tmp_dir)

    ssh = ssh_connect()
    remote_version = get_remote_version(ssh)
    print(f"远程运行版本: {remote_version}")
    #
    need_build = False
    if remote_version != version:
        need_build = True
    if FORCE_DOCKER_BUILD:
        need_build = True

    if need_build:
        build_remote_image(ssh, version)
    #
    # NEW: 启动前先停止旧容器
    stop_old_container(ssh)
    #
    # # 启动新版本
    docker_compose_up(ssh)

    wait_container_status(ssh)

    #
    clean_old_images(ssh, version)


    print(f"🎉 部署完成！当前版本：{version}")


if __name__ == "__main__":
    main()

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

PY_PROJECT_PATH = "../../app/projects/artemis"
REMOTE_DEPLOY_PATH = "/home/machine/docker_deploy/artemis"
REMOTE_HOST = "192.168.31.72"
REMOTE_USER = "machine"
REMOTE_PASS = "123456"
REMOTE_CONFIG_PATH = "/home/machine/data_volume/artemis/config"

DOCKERFILE_PATH = "../docker/dockerfile/Dockerfile-artemis"
DOCKER_COMPOSE_FILE = "artemis.yaml"
DOCKER_COMPOSE_FOLDER = "../docker/docker-compose"

SERVICE_NAME = "artemis"

VPN = "192.168.31.169:7890"

FORCE_DOCKER_BUILD = True
FORCE_DOCKER_COMPOSE_BUILD = True


#########################################
# 工具方法
#########################################

def read_version():
    changelog = Path(PY_PROJECT_PATH) / "CHANGELOG"
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


def create_temp_compose(version):

    tmp_file = os.path.join(Path(PY_PROJECT_PATH).resolve(), "dist", f"artemis-{version}.yaml")
    os.makedirs(os.path.dirname(tmp_file), exist_ok=True)

    if os.path.exists(tmp_file) and not FORCE_DOCKER_COMPOSE_BUILD:
        print(f"✓ compose 文件已存在，跳过: {tmp_file}")
        return tmp_file

    tpl_file = os.path.join(DOCKER_COMPOSE_FOLDER, DOCKER_COMPOSE_FILE)
    with open(tpl_file, "r") as f:
        content = f.read()

    new_lines = []
    for line in content.splitlines():
        if "image:" in line and SERVICE_NAME in line:
            new_lines.append(f"    image: {SERVICE_NAME}:{version}")
        else:
            new_lines.append(line)

    with open(tmp_file, "w") as f:
        f.write("\n".join(new_lines))

    print(f"✔ compose 文件生成: {tmp_file}")
    return tmp_file


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
        try:
            sftp.mkdir(remote_path)
        except IOError:
            pass

        for root, dirs, files in os.walk(local_path):
            rel = os.path.relpath(root, local_path)
            rel = "" if rel == "." else rel

            remote_dir = os.path.join(remote_path, rel).replace("\\", "/")
            try:
                sftp.mkdir(remote_dir)
            except IOError:
                pass

            for filename in files:
                sftp.put(
                    os.path.join(root, filename),
                    os.path.join(remote_dir, filename).replace("\\", "/")
                )
    else:
        sftp.put(local_path, remote_path)

    sftp.close()


def remote_exec(ssh, cmd):
    print(f"🚀 远程执行: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if err:
        print("⚠️ 错误输出:", err)
    return out


def stop_old_container(ssh):
    cmd = f"docker ps --filter 'name={SERVICE_NAME}' --format '{{{{.ID}}}}'"
    cid = remote_exec(ssh, cmd).strip()
    if cid:
        print(f"🛑 停止旧容器: {cid}")
        remote_exec(ssh, f"docker stop {SERVICE_NAME}")
        remote_exec(ssh, f"docker rm {SERVICE_NAME}")
    else:
        print("✔ 没有旧容器")


def get_remote_version(ssh):
    cmd = f"docker ps --filter 'name={SERVICE_NAME}' --format '{{{{.Image}}}}'"
    res = remote_exec(ssh, cmd).strip()
    if ":" in res:
        return res.split(":")[1]
    return None


def build_remote_image(ssh, version):
    print("🔨 开始远程 docker build...")

    # 首先检查代理是否可用
    check_cmd = f"curl -s --connect-timeout 5 http://{VPN}"
    out = remote_exec(ssh, check_cmd)
    if "Connection refused" in out or "timeout" in out:
        print(f"⚠️ 代理 {VPN} 可能不可用，尝试不使用代理")
        # 不使用代理构建
        cmd = (
            f"cd {REMOTE_DEPLOY_PATH} && "
            f"docker build --network=host --progress=plain "
            f"-t {SERVICE_NAME}:{version} ."
        )
    else:
        print(f"✓ 代理 {VPN} 可用")
        # 使用代理构建
        cmd = (
            f"cd {REMOTE_DEPLOY_PATH} && "
            f"export HTTP_PROXY=http://{VPN} HTTPS_PROXY=http://{VPN} && "
            f"docker build --network=host --progress=plain "
            f"--build-arg HTTP_PROXY=http://{VPN} "
            f"--build-arg HTTPS_PROXY=http://{VPN} "
            f"-t {SERVICE_NAME}:{version} ."
        )

    print(cmd)
    print("=== Docker Build ===")

    # 使用更稳定的执行方式
    channel = ssh.get_transport().open_session()
    channel.exec_command(cmd)

    while True:
        if channel.recv_ready():
            data = channel.recv(1024).decode()
            print("BUILD:", data, end="")
        elif channel.recv_stderr_ready():
            data = channel.recv_stderr(1024).decode()
            print("BUILD ERR:", data, end="")
        elif channel.exit_status_ready():
            break
        time.sleep(0.1)

    exit_code = channel.recv_exit_status()
    if exit_code != 0:
        print(f"❌ Docker build 失败，退出码: {exit_code}")
        sys.exit(1)
def docker_compose_up(ssh):
    cmd = f"cd {REMOTE_DEPLOY_PATH} && docker compose -f docker-compose.yaml up -d"
    remote_exec(ssh, cmd)
    print("✔ docker compose 启动完成")


def clean_old_images(ssh, version):
    # 删除旧版本镜像
    cmd = f"docker images {SERVICE_NAME} --format '{{{{.Tag}}}}'"
    tags = remote_exec(ssh, cmd).splitlines()
    for t in tags:
        if t and t != version:
            print(f"🧹 删除旧镜像: {t}")
            remote_exec(ssh, f"docker rmi {SERVICE_NAME}:{t}")

    # 删除 dangling image (<none>)
    print("🧹 删除悬空镜像 (<none>)")
    remote_exec(ssh, "docker image prune -f")



def wait_container(ssh, timeout=60):
    for i in range(timeout):
        status = remote_exec(
            ssh,
            f"docker ps -a --filter 'name={SERVICE_NAME}' --format '{{{{.Status}}}}'"
        ).strip()

        if status.startswith("Up"):
            print("🎉 Artemis 启动成功")
            return

        if "Exited" in status or "Restarting" in status:
            print("❌ Artemis 启动失败")
            logs = remote_exec(ssh, f"docker logs {SERVICE_NAME}")
            print(logs)
            sys.exit(1)

        time.sleep(1)

    print("❌ Artemis 启动超时")
    sys.exit(1)


def upload_files(compose_file):
    print("⬆️ 上传构建产物和 docker 文件...")

    ssh = ssh_connect()

    sftp_upload(ssh, PY_PROJECT_PATH, f"{REMOTE_DEPLOY_PATH}/artemis")
    sftp_upload(ssh, PY_PROJECT_PATH+"/requirements.txt", f"{REMOTE_DEPLOY_PATH}/requirements.txt")
    sftp_upload(ssh, DOCKERFILE_PATH, f"{REMOTE_DEPLOY_PATH}/Dockerfile")
    sftp_upload(ssh, compose_file, f"{REMOTE_DEPLOY_PATH}/docker-compose.yaml")
    sftp_upload(ssh, PY_PROJECT_PATH+"/config/config-prod.yaml", f"{REMOTE_CONFIG_PATH}/config.yaml")
    sftp_upload(ssh, PY_PROJECT_PATH+"/config/task.yaml", f"{REMOTE_CONFIG_PATH}/task.yaml")

    ssh.close()


#########################################
# --------------- 主流程 ----------------
#########################################

def main():
    version = read_version()

    compose_file = create_temp_compose(version)

    ssh = ssh_connect()

    print("⬆️ 上传 Python 项目文件...")
    upload_files(compose_file)
    #
    remote_version = get_remote_version(ssh)
    print("远程版本:", remote_version)
    #
    need_build = FORCE_DOCKER_BUILD or (remote_version != version)
    #
    if need_build:
        build_remote_image(ssh, version)
    #
    stop_old_container(ssh)
    #
    docker_compose_up(ssh)
    #
    wait_container(ssh)
    #
    clean_old_images(ssh, version)
    #
    # print(f"🎉 部署成功！当前版本：{version}")


if __name__ == "__main__":
    main()

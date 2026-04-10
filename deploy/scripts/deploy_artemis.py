#!/usr/bin/env python3
import os
import paramiko
import sys
from pathlib import Path
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

PRIMARY_PROXY = "192.168.31.170:7890"
BACKUP_PROXY  = "192.168.31.169:7890"

BASE_IMAGE = "python:3.11-slim"

FORCE_DOCKER_BUILD = True
FORCE_DOCKER_COMPOSE_BUILD = True

# Path to local folder containing wheel files that should be included in build context
MINIUS_LOCAL_PATH = "../../minius"


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


def pull_base_image(ssh, proxy):
    """先用代理拉取基础镜像，避免 build 时 buildkit 直连超时"""
    print(f"📦 拉取基础镜像: {BASE_IMAGE}")
    cmd = f"docker pull {BASE_IMAGE}"
    if proxy:
        cmd = f"HTTP_PROXY=http://{proxy} HTTPS_PROXY=http://{proxy} {cmd}"

    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=600)

    import sys as _sys
    while True:
        if stdout.channel.recv_ready():
            _sys.stdout.write(stdout.channel.recv(1024).decode())
            _sys.stdout.flush()
        if stdout.channel.exit_status_ready() and not stdout.channel.recv_ready():
            break
        time.sleep(0.1)

    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        err = stderr.read().decode().strip()
        print(f"⚠️ 拉取基础镜像失败: {err}")
        return False
    print(f"✔ 基础镜像拉取完成: {BASE_IMAGE}")
    return True


def build_remote_image(ssh, version):
    print("🔨 开始远程 docker build...")

    proxy = detect_remote_proxy(ssh)

    # 先拉基础镜像（buildkit 拉镜像不读 --build-arg 代理）
    pull_base_image(ssh, proxy)

    cmd = f"cd {REMOTE_DEPLOY_PATH} && docker build --network=host --progress=plain"
    if proxy:
        cmd += f" --build-arg HTTP_PROXY=http://{proxy} --build-arg HTTPS_PROXY=http://{proxy}"
    cmd += f" -t {SERVICE_NAME}:{version} ."

    print(f"执行命令: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=600)

    import sys as _sys
    while True:
        if stdout.channel.recv_ready():
            data = stdout.channel.recv(1024).decode()
            _sys.stdout.write(data)
            _sys.stdout.flush()
        if stderr.channel.recv_stderr_ready():
            data = stderr.channel.recv_stderr(1024).decode()
            _sys.stderr.write(data)
            _sys.stderr.flush()
        if stdout.channel.exit_status_ready() and not stdout.channel.recv_ready() and not stderr.channel.recv_stderr_ready():
            break
        time.sleep(0.1)

    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        print(f"❌ Docker build 失败，退出码: {exit_code}")
        sys.exit(1)
    print("✅ Docker build 成功")
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

    # Upload the canonical Dockerfile from the repo (we updated it to COPY minius and install wheels)
    dockerfile_local_path = os.path.normpath(os.path.join(os.path.dirname(__file__), DOCKERFILE_PATH))
    sftp_upload(ssh, dockerfile_local_path, f"{REMOTE_DEPLOY_PATH}/Dockerfile")

    sftp_upload(ssh, compose_file, f"{REMOTE_DEPLOY_PATH}/docker-compose.yaml")
    sftp_upload(ssh, PY_PROJECT_PATH+"/config/config-production.yaml", f"{REMOTE_CONFIG_PATH}/config.yaml")
    sftp_upload(ssh, PY_PROJECT_PATH+"/config/task.yaml", f"{REMOTE_CONFIG_PATH}/task.yaml")

    # Upload only wheel files from local minius directory. Abort if minius missing or no wheels found.
    local_minius = os.path.normpath(os.path.join(os.path.dirname(__file__), MINIUS_LOCAL_PATH))
    if not os.path.exists(local_minius) or not os.path.isdir(local_minius):
        print(f"❌ 本地依赖目录不存在或不是目录: {local_minius}，部署中止。请将 minius 目录放在项目根目录下并包含 wheel 文件。")
        ssh.close()
        sys.exit(1)

    wheel_files = [f for f in os.listdir(local_minius) if f.lower().endswith('.whl')]
    if not wheel_files:
        print(f"❌ 在 {local_minius} 中未找到任何 .whl 文件，部署中止。请把需要的 wheels 放入该目录。")
        ssh.close()
        sys.exit(1)

    # ensure remote minius directory exists
    remote_exec(ssh, f"mkdir -p {REMOTE_DEPLOY_PATH}/minius")

    for wf in wheel_files:
        local_wheel = os.path.join(local_minius, wf)
        remote_wheel = f"{REMOTE_DEPLOY_PATH}/minius/{wf}"
        print(f"⬆️ 上传 wheel: {local_wheel} -> {remote_wheel}")
        sftp_upload(ssh, local_wheel, remote_wheel)

    ssh.close()

def detect_remote_proxy(ssh):
    """从远程服务器检测可用的代理"""
    print("🔍 检测远程服务器代理...")
    for name, proxy_url in [("主代理", PRIMARY_PROXY), ("备用代理", BACKUP_PROXY)]:
        cmd = f'curl --connect-timeout 3 --silent --proxy http://{proxy_url} -o /dev/null -w "%{{http_code}}" https://www.google.com 2>/dev/null'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        code = stdout.read().decode().strip()
        if code == "200":
            print(f"✅ 远程{name}可用: http://{proxy_url}")
            return proxy_url
        print(f"   {name}不可达: http://{proxy_url}")
    print("⚠️ 远程无可用代理")
    return None
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

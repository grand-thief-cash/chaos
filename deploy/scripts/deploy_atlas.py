#!/usr/bin/env python3
"""Build and deploy Atlas using the same cached-base-image pattern as Artemis."""

from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

import paramiko


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
PROJECT_PATH = REPO_ROOT / "app" / "projects" / "atlas"
DOCKERFILE = REPO_ROOT / "deploy" / "docker" / "dockerfile" / "Dockerfile-atlas"
BASE_DOCKERFILE = (
    REPO_ROOT / "deploy" / "docker" / "dockerfile" / "Dockerfile-atlas-base"
)
COMPOSE_TEMPLATE = (
    REPO_ROOT / "deploy" / "docker" / "docker-compose" / "atlas.yaml"
)

SERVICE_NAME = "atlas"
REMOTE_HOST = os.getenv("CHAOS_DEPLOY_HOST", "192.168.31.72")
REMOTE_USER = os.getenv("CHAOS_DEPLOY_USER", "machine")
REMOTE_PASSWORD = os.getenv("CHAOS_DEPLOY_PASSWORD", "")
REMOTE_DEPLOY_PATH = "/home/machine/docker_deploy/atlas"
REMOTE_CONFIG_PATH = "/home/machine/data_volume/atlas/config"
UPLOAD_CONFIG = os.getenv("ATLAS_UPLOAD_CONFIG", "0") == "1"


def read_version() -> str:
    for line in (PROJECT_PATH / "CHANGELOG").read_text(encoding="utf-8").splitlines():
        candidate = line.strip()
        if candidate.startswith("v"):
            return candidate
    raise RuntimeError("Atlas CHANGELOG does not contain a version line")


def dependency_tag() -> str:
    digest = hashlib.sha256(
        (PROJECT_PATH / "requirements.txt").read_bytes()
    ).hexdigest()
    return digest[:12]


def create_compose(version: str) -> Path:
    content = COMPOSE_TEMPLATE.read_text(encoding="utf-8")
    content = content.replace("image: atlas:v1.0.0", f"image: atlas:{version}")
    output = PROJECT_PATH / "dist" / f"atlas-{version}.yaml"
    output.parent.mkdir(exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output


def connect() -> paramiko.SSHClient:
    if not REMOTE_PASSWORD:
        raise RuntimeError("CHAOS_DEPLOY_PASSWORD must be set")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        REMOTE_HOST,
        username=REMOTE_USER,
        password=REMOTE_PASSWORD,
    )
    return client


def remote_exec(client: paramiko.SSHClient, command: str) -> str:
    _, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode("utf-8", errors="replace")
    error = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        raise RuntimeError(
            f"remote command failed ({exit_code}): {command}\n{error}"
        )
    return output


def ensure_remote_directory(client: paramiko.SSHClient, path: str) -> None:
    remote_exec(client, f"mkdir -p {path}")


def upload_file(
    client: paramiko.SSHClient,
    local: Path,
    remote: str,
) -> None:
    with client.open_sftp() as sftp:
        sftp.put(str(local), remote)


def upload_tree(
    client: paramiko.SSHClient,
    local: Path,
    remote: str,
) -> None:
    ensure_remote_directory(client, remote)
    with client.open_sftp() as sftp:
        for root, directories, files in os.walk(local):
            root_path = Path(root)
            relative = root_path.relative_to(local)
            remote_root = (
                remote
                if str(relative) == "."
                else f"{remote}/{relative.as_posix()}"
            )
            try:
                sftp.mkdir(remote_root)
            except OSError:
                pass
            for directory in directories:
                try:
                    sftp.mkdir(f"{remote_root}/{directory}")
                except OSError:
                    pass
            for filename in files:
                sftp.put(
                    str(root_path / filename),
                    f"{remote_root}/{filename}",
                )


def upload_build_context(
    client: paramiko.SSHClient,
    compose: Path,
) -> None:
    ensure_remote_directory(client, REMOTE_DEPLOY_PATH)
    remote_exec(client, f"rm -rf {REMOTE_DEPLOY_PATH}/atlas")
    upload_tree(
        client,
        PROJECT_PATH / "atlas",
        f"{REMOTE_DEPLOY_PATH}/atlas",
    )
    upload_file(
        client,
        PROJECT_PATH / "requirements.txt",
        f"{REMOTE_DEPLOY_PATH}/requirements.txt",
    )
    upload_file(client, DOCKERFILE, f"{REMOTE_DEPLOY_PATH}/Dockerfile")
    upload_file(
        client,
        BASE_DOCKERFILE,
        f"{REMOTE_DEPLOY_PATH}/Dockerfile-base",
    )
    upload_file(client, compose, f"{REMOTE_DEPLOY_PATH}/docker-compose.yaml")

    ensure_remote_directory(client, f"{REMOTE_CONFIG_PATH}/semantic")
    config_exists = remote_exec(
        client,
        f"if test -f {REMOTE_CONFIG_PATH}/config.yaml; "
        "then echo yes; else echo no; fi",
    ).strip() == "yes"
    if UPLOAD_CONFIG or not config_exists:
        upload_file(
            client,
            PROJECT_PATH / "config" / "config-production.yaml",
            f"{REMOTE_CONFIG_PATH}/config.yaml",
        )
    mapping_exists = remote_exec(
        client,
        f"if test -f {REMOTE_CONFIG_PATH}/report_prompt_mapping.yaml; "
        "then echo yes; else echo no; fi",
    ).strip() == "yes"
    if UPLOAD_CONFIG or not mapping_exists:
        upload_file(
            client,
            PROJECT_PATH / "config" / "report_prompt_mapping.yaml",
            f"{REMOTE_CONFIG_PATH}/report_prompt_mapping.yaml",
        )
    seed_exists = remote_exec(
        client,
        f"if test -f {REMOTE_CONFIG_PATH}/semantic/atlas-semantic-v0001.yaml; "
        "then echo yes; else echo no; fi",
    ).strip() == "yes"
    if UPLOAD_CONFIG or not seed_exists:
        upload_tree(
            client,
            PROJECT_PATH / "config" / "semantic",
            f"{REMOTE_CONFIG_PATH}/semantic",
        )


def ensure_base_image(client: paramiko.SSHClient, tag: str) -> None:
    image = f"atlas-base:{tag}"
    if remote_exec(client, f"docker images -q {image}").strip():
        return
    remote_exec(
        client,
        f"cd {REMOTE_DEPLOY_PATH} && "
        "docker build --network=host --progress=plain "
        f"-f Dockerfile-base -t {image} .",
    )


def build_application_image(
    client: paramiko.SSHClient,
    version: str,
    base_tag: str,
) -> None:
    remote_exec(
        client,
        f"cd {REMOTE_DEPLOY_PATH} && "
        "docker build --network=host --progress=plain "
        f"--build-arg BASE_TAG={base_tag} "
        f"-t {SERVICE_NAME}:{version} .",
    )


def deploy(client: paramiko.SSHClient) -> None:
    remote_exec(
        client,
        f"cd {REMOTE_DEPLOY_PATH} && "
        "docker compose -f docker-compose.yaml up -d --force-recreate",
    )


def wait_until_healthy(
    client: paramiko.SSHClient,
    timeout_seconds: int = 90,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = remote_exec(
            client,
            "docker inspect --format "
            "'{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "
            f"{SERVICE_NAME}",
        ).strip()
        if status == "healthy":
            return
        if status in {"exited", "dead", "unhealthy"}:
            logs = remote_exec(
                client,
                f"docker logs --tail 200 {SERVICE_NAME}",
            )
            raise RuntimeError(f"Atlas failed to start:\n{logs}")
        time.sleep(2)
    raise TimeoutError("Atlas did not become healthy within 90 seconds")


def main() -> int:
    version = read_version()
    base_tag = dependency_tag()
    compose = create_compose(version)
    client = connect()
    try:
        upload_build_context(client, compose)
        ensure_base_image(client, base_tag)
        build_application_image(client, version, base_tag)
        deploy(client)
        wait_until_healthy(client)
    finally:
        client.close()
    print(f"Atlas {version} is healthy on {REMOTE_HOST}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

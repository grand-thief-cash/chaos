from __future__ import annotations

from pathlib import Path
import re

import yaml

from atlas.models import SemanticVersion


class SemanticYamlPublisher:
    """Publish an immutable semantic artifact with an atomic same-directory replace."""

    def __init__(self, semantic_directory: str | Path) -> None:
        self.semantic_directory = Path(semantic_directory)

    def publish(self, version: SemanticVersion) -> Path:
        if not re.fullmatch(r"atlas-semantic-v\d{4,}", version.version):
            raise ValueError("invalid semantic version name")
        self.semantic_directory.mkdir(parents=True, exist_ok=True)
        target = self.semantic_directory / f"{version.version}.yaml"
        if target.exists():
            raise FileExistsError(f"semantic version already exists: {version.version}")
        temporary = target.with_suffix(".yaml.tmp")
        temporary.write_text(
            yaml.safe_dump(
                version.model_dump(mode="json"),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        temporary.replace(target)
        return target

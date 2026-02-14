from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

from artemis.models.runtime_update import TaskUnitTreeNode


@dataclass(frozen=True)
class TaskYamlInfo:
    path: Path
    content: str


class RuntimeFileService:
    def __init__(self) -> None:
        base_dir = Path(__file__).parent.parent
        self._task_units_root = base_dir / "task_units"
        self._task_yaml_paths = [
            base_dir / "config" / "task.yaml",
            base_dir.parent / "config" / "task.yaml",
        ]

    def resolve_task_yaml(self) -> Path:
        for path in self._task_yaml_paths:
            if path.exists():
                return path
        return self._task_yaml_paths[0]

    def read_task_yaml(self) -> TaskYamlInfo:
        path = self.resolve_task_yaml()
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        return TaskYamlInfo(path=path, content=content)

    def write_task_yaml(self, content: str) -> TaskYamlInfo:
        yaml.safe_load(content)  # validate
        path = self.resolve_task_yaml()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return TaskYamlInfo(path=path, content=content)

    def task_units_root(self) -> Path:
        return self._task_units_root

    def build_task_units_tree(self) -> List[TaskUnitTreeNode]:
        root = self._task_units_root
        if not root.exists():
            return []

        def build_node(path: Path) -> TaskUnitTreeNode | None:
            if path.is_dir():
                children = []
                for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
                    if child.name.startswith("__pycache__"):
                        continue
                    node = build_node(child)
                    if node:
                        children.append(node)
                return TaskUnitTreeNode(name=path.name, type="dir", children=children)
            if path.suffix != ".py":
                return None
            return TaskUnitTreeNode(name=path.name, type="file")

        items: List[TaskUnitTreeNode] = []
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            node = build_node(child)
            if node:
                items.append(node)
        return items

    def _resolve_task_unit_path(self, rel_path: str) -> Path:
        if not rel_path or rel_path.strip() == "":
            raise ValueError("path is required")
        candidate = Path(rel_path)
        if candidate.is_absolute():
            raise ValueError("absolute path not allowed")
        if ".." in candidate.parts:
            raise ValueError("path traversal not allowed")
        if candidate.suffix != ".py":
            raise ValueError("only .py files are supported")
        full = (self._task_units_root / candidate).resolve()
        if self._task_units_root.resolve() not in full.parents and full != self._task_units_root.resolve():
            raise ValueError("path must be within task_units")
        return full

    def read_task_unit(self, rel_path: str) -> str:
        path = self._resolve_task_unit_path(rel_path)
        if not path.exists():
            raise FileNotFoundError(f"{rel_path} not found")
        return path.read_text(encoding="utf-8")

    def write_task_unit(self, rel_path: str, content: str, create: bool = False) -> Path:
        path = self._resolve_task_unit_path(rel_path)
        if path.exists() and create:
            raise FileExistsError(f"{rel_path} already exists")
        if not path.exists() and not create:
            raise FileNotFoundError(f"{rel_path} not found")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

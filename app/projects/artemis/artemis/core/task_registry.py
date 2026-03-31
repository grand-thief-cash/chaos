import yaml
import importlib
import sys
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Type, Dict, Optional, List

from artemis.consts import TaskCode


@dataclass(frozen=True)
class TaskSpec:
    module: str
    class_name: str
    is_dynamic: bool = False

    def resolve(self) -> Type:
        module = importlib.import_module(self.module)
        if module.__name__ in sys.modules:
            module = importlib.reload(module)
        try:
            return getattr(module, self.class_name)
        except AttributeError as exc:
            raise ValueError(f"Task class '{self.class_name}' not found in module '{self.module}'") from exc


class TaskRegistry:
    def __init__(self):
        self._registry: Dict[str, TaskSpec] = {}
        # Assuming artemis/config relative to artemis/core or project root
        # Using __file__ (artemis/core/task_registry.py) -> artemis/config/registrations.yaml
        self._config_path = Path(__file__).parent.parent.parent / "config" / "registrations.yaml"
        self._load_dynamic_tasks()

    def _load_dynamic_tasks(self):
        if not self._config_path.exists():
            return

        try:
            content = self._config_path.read_text(encoding="utf-8")
            if not content.strip():
                return

            data = yaml.safe_load(content) or {}
            for code, info in data.items():
                try:
                    self.register(
                        task_code=code,
                        module=info.get("module"),
                        class_name=info.get("class_name"),
                        is_dynamic=True,
                        persist=False # Avoid infinite loop
                    )
                except Exception as e:
                    print(f"Failed to load dynamic task {code}: {e}")
        except Exception as e:
            print(f"Failed to read registrations file: {e}")

    def _save_dynamic_tasks(self):
        data = {}
        for code, spec in self._registry.items():
            if spec.is_dynamic:
                data[code] = {
                    "module": spec.module,
                    "class_name": spec.class_name
                }

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)

    @staticmethod
    def _normalize_key(task_code: TaskCode | str) -> str:
        if isinstance(task_code, TaskCode):
            key = task_code.value
        else:
            key = str(task_code)
        key = key.strip()
        if not key:
            raise ValueError("task_code cannot be empty")
        return key

    def register(
        self,
        task_code: TaskCode | str,
        cls: Optional[Type] = None,
        module: Optional[str] = None,
        class_name: Optional[str] = None,
        is_dynamic: bool = False,
        persist: bool = True
    ):
        key = self._normalize_key(task_code)
        if key in self._registry:
            # Optionally allow overwriting if it's the exact same spec to avoid reload errors?
            # But strict for now.
             raise ValueError(f"Task '{key}' already registered")

        if cls is not None:
            spec = TaskSpec(module=cls.__module__, class_name=cls.__name__, is_dynamic=is_dynamic)
        else:
            if not module or not class_name:
                raise ValueError("register requires either cls or module+class_name")
            spec = TaskSpec(module=module, class_name=class_name, is_dynamic=is_dynamic)

        self._registry[key] = spec

        if is_dynamic and persist:
            self._save_dynamic_tasks()

    def unregister(self, task_code: TaskCode | str):
        key = self._normalize_key(task_code)
        spec = self._registry.get(key)
        if not spec:
            raise ValueError(f"Task '{key}' not registered")

        if not spec.is_dynamic:
            raise ValueError(f"Task '{key}' is not dynamic and cannot be unregistered")

        del self._registry[key]
        self._save_dynamic_tasks()

    def has_task(self, task_code: TaskCode | str) -> bool:
        key = self._normalize_key(task_code)
        return key in self._registry

    def get_task_spec(self, task_code: TaskCode | str) -> Optional[TaskSpec]:
        key = self._normalize_key(task_code)
        return self._registry.get(key)

    def get_task(self, task_code: TaskCode | str):
        spec = self.get_task_spec(task_code)
        if not spec:
            return None
        return spec.resolve()

    def list_tasks(self) -> Dict[str, TaskSpec]:
        """Return a shallow copy of the registry mapping task code to task spec."""
        return dict(self._registry)

    def scan_unregistered(self) -> List[Dict[str, str]]:
        """
        Scans the task_units directory for classes that inherit from BaseTaskUnit
        but are not currently registered in the task registry.
        """
        from artemis.task_units.base import BaseTaskUnit # Import locally to avoid circular dependency
        unregistered = []

        # Base directory for task units
        # Assuming artemis/artemis/core/task_registry.py -> artemis/artemis/task_units
        base_dir = Path(__file__).parent.parent / "task_units"
        if not base_dir.exists():
            return []

        # Walk through the directory to find python files
        for file_path in base_dir.rglob("*.py"):
            if file_path.name.startswith("__") or file_path.name in ["base.py", "consts.py"]:
                continue

            # Convert file path to module path
            parts = file_path.parts
            try:
                # find the index of the last 'artemis'
                # e.g. /app/projects/artemis/artemis/task_units/zh/stock.py
                # we want module: artemis.task_units.zh.stock
                # Logic: find 'artemis' followed by 'task_units'

                # Simple heuristic: find right-most 'artemis' folder in path because that's the package root
                # If path has multiple 'artemis', we usually want the one containing 'task_units'

                # Check for 'artemis' in parts
                indices = [i for i, part in enumerate(parts) if part == 'artemis']
                if not indices:
                    continue

                # Use the last one as package root
                artemis_index = indices[-1]
                module_parts = parts[artemis_index:]
                module_name = ".".join(module_parts).replace(".py", "")

            except ValueError:
                continue

            try:
                module = importlib.import_module(module_name)
                # Inspect members
                for name, obj in inspect.getmembers(module):
                    # Filter logic:
                    # 1. Must be a class.
                    # 2. Must inherit from BaseTaskUnit and not be BaseTaskUnit itself.
                    # 3. Must be defined in this module (not imported).
                    if (inspect.isclass(obj) and
                        issubclass(obj, BaseTaskUnit) and
                        obj is not BaseTaskUnit and
                        obj.__module__ == module.__name__
                    ):
                        # Filter out known abstract/base classes
                        if name in ['ChildTaskUnit', 'OrchestratorTaskUnit', 'TaskContext']:
                            continue

                        # Found a task class
                        # Check if it is already registered
                        is_registered = False
                        for reg_code, reg_spec in self._registry.items():
                            # Check if registered under THIS module or any alias (less strict)
                            if reg_spec.module == module_name and reg_spec.class_name == name:
                                is_registered = True
                                break

                        if not is_registered:
                            # Try to find a suggested code
                            task_code = getattr(obj, 'TASK_CODE', None)
                            if not task_code:
                                # Fallback: UPPER_CASE_SNAKE_CASE from ClassName
                                # Simple conversion: StockZHAListDailyTask -> STOCK_ZH_A_LIST_DAILY_TASK
                                import re
                                s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
                                task_code = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).upper()

                            unregistered.append({
                                "module": module_name,
                                "class_name": name,
                                "task_code": task_code
                            })
            except Exception:
                # skipping files that cannot be imported
                continue

        return unregistered

registry = TaskRegistry()

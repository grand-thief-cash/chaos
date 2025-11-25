"""TaskUnit Template

Usage:
1. Copy this file to `task_units/<domain>/<task_name>/unit.py`.
2. Adjust `TASK_CODE` and implement needed lifecycle methods.
3. Register at bottom: `task_registry.register(TASK_CODE, <ClassName>)`.
"""
from typing import Iterable, Any, List

from artemis.core.context import TaskContext
from artemis.task_units.base import BaseTaskUnit

TASK_CODE = 'replace_me'

class ExampleTaskUnit(BaseTaskUnit):
    def prepare_params(self, ctx: TaskContext):  # optional override
        super().prepare_params(ctx)
        # Add validation or computed params
        ctx.params.setdefault('foo', 'bar')
        if ctx.logger:
            ctx.logger.info({'event': 'template_prepare_params'})

    def build_sources(self, ctx: TaskContext):  # optional
        return []

    def fetch(self, ctx: TaskContext) -> Iterable[Any]:
        # Yield mock records (replace with real fetch logic)
        yield {'demo': True}

    def process(self, records: Iterable[Any], ctx: TaskContext) -> List[Any]:
        # Transform records as needed
        return list(records)

    def decide_sinks(self, ctx: TaskContext):
        # Reuse default sink decision or customize
        return super().decide_sinks(ctx)

    def emit(self, processed: List[Any], ctx: TaskContext):
        super().emit(processed, ctx)

    def finalize(self, ctx: TaskContext):
        ctx.stats['status'] = 'ok'

# Uncomment to register when adapted
# task_registry.register(TASK_CODE, ExampleTaskUnit)


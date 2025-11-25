from artemis.core.context import TaskContext
from typing import Any, Iterable, List


class BaseTaskUnit:
    def prepare_params(self, ctx: TaskContext):
        # merge defaults
        from artemis.core.config import task_default
        defaults = task_default(ctx.task_code)
        merged = {**defaults, **ctx.incoming_params}
        ctx.params = merged
        if ctx.logger:
            ctx.logger.info({'event': 'prepare_params', 'params_keys': list(merged.keys())})

    def build_sources(self, ctx: TaskContext):
        return []  # override

    def fetch(self, ctx: TaskContext) -> Iterable[Any]:
        return []  # override

    def process(self, records: Iterable[Any], ctx: TaskContext) -> List[Any]:
        return list(records)

    def decide_sinks(self, ctx: TaskContext):
        from artemis.core.config import output_default
        out_cfg = output_default(ctx.task_code)
        sinks = out_cfg.get('sinks', [])
        resolved = []
        if 'http' in sinks:
            from artemis.sinks.http_sink import HttpSink
            resolved.append(HttpSink(out_cfg.get('http_endpoint')))
        return resolved

    def emit(self, processed: List[Any], ctx: TaskContext):
        sinks = self.decide_sinks(ctx)
        for s in sinks:
            s.emit(processed, ctx)
        ctx.stats['records_emitted'] = len(processed)

    def finalize(self, ctx: TaskContext):
        ctx.stats.setdefault('status', 'ok')

    def run(self, ctx: TaskContext):
        self.prepare_params(ctx)
        records = self.fetch(ctx)
        processed = self.process(records, ctx)
        self.emit(processed, ctx)
        self.finalize(ctx)


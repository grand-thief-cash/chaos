from artemis.core import task_registry
from artemis.task_units.base import BaseTaskUnit

class LongTaskUnit(BaseTaskUnit):
    TOTAL = 50

    def before_execute(self, ctx):
        # apply variant config if provided
        total = ctx.params.get('total')
        if isinstance(total, int) and total > 0:
            self.TOTAL = total

    def execute(self, ctx):
        # simulate incremental progress updates during execution
        for i in range(self.TOTAL):
            if i % 10 == 0 and getattr(ctx, 'callback', None):
                try:
                    ctx.callback.progress(i, self.TOTAL, message=f"processed {i}")
                except Exception:
                    pass
        # return a simple result for post_process/sink
        return {'processed': self.TOTAL}

    def sink(self, ctx, processed):
        # no-op sink for example; just record stats
        ctx.stats['records_emitted'] = processed.get('processed', 0)

# register example task
try:
    task_registry.register('long_task_example', LongTaskUnit)
except Exception:
    pass

from artemis.core import task_registry
from artemis.task_units.base import BaseTaskUnit

class LongTaskUnit(BaseTaskUnit):
    TOTAL = 50

    def fetch(self, ctx):
        # simulate incremental progress updates
        for i in range(self.TOTAL):
            # update progress every 10 items
            if i % 10 == 0 and getattr(ctx, 'callback', None):
                try:
                    ctx.callback.progress(i, self.TOTAL, message=f"processed {i}")
                except Exception:
                    pass
            yield {'index': i}

    def finalize(self, ctx):
        super().finalize(ctx)
        ctx.stats['status'] = 'ok'

# register example task
try:
    task_registry.register('long_task_example', LongTaskUnit)
except Exception:
    pass


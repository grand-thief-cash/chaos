import random
import time

from artemis.core import task_registry
from artemis.task_units.base import BaseTaskUnit


class LongTaskUnit(BaseTaskUnit):
    TOTAL = 50

    def fetch(self, ctx):
        # simulate incremental progress updates
        for i in range(1, self.TOTAL + 1):
            # update progress every 10 items
            time.sleep(0.5 + random.random() * 0.2)
            ctx.callback.progress(i, self.TOTAL, message=f"processed {i}")
            yield {'index': i}

    def finalize(self, ctx):
        super().finalize(ctx)
        ctx.stats['status'] = 'ok'

# register example task
try:
    task_registry.register('long_task_example', LongTaskUnit)
except Exception:
    pass


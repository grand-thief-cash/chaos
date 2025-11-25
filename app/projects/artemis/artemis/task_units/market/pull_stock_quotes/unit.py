from artemis.core import task_registry
from artemis.sources.rest_source import RestPriceSource
from artemis.task_units.base import BaseTaskUnit


class PullStockQuotesUnit(BaseTaskUnit):
    def build_sources(self, ctx):
        symbols = ctx.params.get('symbols', [])
        return [RestPriceSource(symbols)]

    def fetch(self, ctx):
        for src in self.build_sources(ctx):
            for rec in src.fetch(ctx.params, ctx):
                yield rec

# register
task_registry.register('pull_stock_quotes', PullStockQuotesUnit)

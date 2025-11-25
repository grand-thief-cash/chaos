from typing import Iterable, Any, List

from artemis.core.context import TaskContext
from artemis.models.record import Record


class RestPriceSource:
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
    def fetch(self, params: dict, ctx: TaskContext) -> Iterable[Any]:
        for sym in self.symbols:
            yield Record(symbol=sym, price=123.45, timestamp='2025-11-12T00:00:00Z')

"""BI service package over phoenixA raw data APIs.

Architecture: phoenixA is the data middle-platform (raw queries, field
discovery, coverage) and does no business computation. artemis is the BI
backend: it forwards raw passthrough queries for simple needs AND owns
business computation (aggregation, ratios, period-over-period deltas) for
analytical features like DuPont. cthulhu calls artemis /bi/* endpoints.

The service is split by business area (see the modules in this package) and
combined into :class:`BIService`.
"""
from artemis.services.bi.service import BIService

__all__ = ["BIService"]

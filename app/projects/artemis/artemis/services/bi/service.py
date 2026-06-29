"""BIService — the public BI service.

Combines the passthrough mixins (securities, discovery, raw queries) with the
DuPont analytical-computation mixin over phoenixA. cthulhu calls artemis /bi/*
endpoints, which delegate here.
"""
from __future__ import annotations

from artemis.services.bi.base import BIServiceBase
from artemis.services.bi.discovery import DiscoveryMixin
from artemis.services.bi.dupont import DupontMixin
from artemis.services.bi.raw_queries import RawQueryMixin
from artemis.services.bi.securities import SecuritiesMixin


class BIService(
    SecuritiesMixin,
    DiscoveryMixin,
    RawQueryMixin,
    DupontMixin,
):
    """BI service: raw passthrough + analytical computation over phoenixA."""

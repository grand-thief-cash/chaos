"""BIService — the public BI service.

Combines the passthrough mixins (discovery, raw queries) with the DuPont
analytical-computation mixin over phoenixA. cthulhu calls artemis /bi/*
endpoints, which delegate here. Securities lookup lives in the general
``SecuritiesService`` (shared by /securities and the legacy /bi/securities).
"""
from __future__ import annotations

from artemis.services.bi.base import BIServiceBase
from artemis.services.bi.discovery import DiscoveryMixin
from artemis.services.bi.dupont import DupontMixin
from artemis.services.bi.raw_queries import RawQueryMixin


class BIService(
    DiscoveryMixin,
    RawQueryMixin,
    DupontMixin,
):
    """BI service: raw passthrough + analytical computation over phoenixA."""

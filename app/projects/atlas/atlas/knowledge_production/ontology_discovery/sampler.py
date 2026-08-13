from __future__ import annotations

import hashlib
import re
from collections import defaultdict, deque
from collections.abc import Sequence

from atlas.models import ResearchReport


_SUBTYPE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("业绩点评", re.compile(r"年报|季报|中报|业绩|财报|预告|快报")),
    ("事件点评", re.compile(r"点评|事件|公告|签约|中标|收购|回购|增持|减持")),
    ("公司深度", re.compile(r"深度|首次覆盖|公司研究|投资价值|专题")),
    ("行业周期", re.compile(r"周报|月报|旬报|日报|跟踪|景气")),
    ("策略", re.compile(r"策略|展望|配置|复盘")),
    ("晨报", re.compile(r"晨报|早报|早会")),
)


def infer_report_subtype(report: ResearchReport) -> str:
    title = report.title or ""
    for subtype, pattern in _SUBTYPE_RULES:
        if pattern.search(title):
            return subtype
    return "其他"


def _stable_order(report: ResearchReport, seed: int) -> tuple[str, str, str]:
    digest = hashlib.sha256(
        f"{seed}:{report.document_id}:{report.title}".encode("utf-8")
    ).hexdigest()
    return digest, report.publish_date, report.resource_id


def stratified_sample(
    reports: Sequence[ResearchReport], sample_size: int, *, seed: int = 0
) -> list[ResearchReport]:
    """Balance report type, title-derived subtype and institution.

    Stable hashing removes the previous newest-document bias. Changing ``seed``
    produces a reproducible alternative sample rather than selecting the same
    few PDFs on every iteration.
    """
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    strata: dict[tuple[str, str, str], list[ResearchReport]] = defaultdict(list)
    for report in reports:
        strata[(
            report.report_type,
            infer_report_subtype(report),
            report.org_name or "UNKNOWN_INSTITUTION",
        )].append(report)
    # Balance report types first. A single flat queue sorted by
    # (report_type, subtype, institution) can spend a small sample entirely on
    # the alphabetically first report type when it has many strata.
    queues_by_type: dict[str, deque[deque[ResearchReport]]] = defaultdict(deque)
    for (report_type, _subtype, _institution), items in sorted(strata.items()):
        queues_by_type[report_type].append(
            deque(sorted(items, key=lambda item: _stable_order(item, seed)))
        )
    report_type_queues = deque(
        (report_type, queues_by_type[report_type])
        for report_type in sorted(queues_by_type)
    )
    result: list[ResearchReport] = []
    while report_type_queues and len(result) < sample_size:
        report_type, type_strata = report_type_queues.popleft()
        stratum = type_strata.popleft()
        result.append(stratum.popleft())
        if stratum:
            type_strata.append(stratum)
        if type_strata:
            report_type_queues.append((report_type, type_strata))
    return result

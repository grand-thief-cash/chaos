from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence

from atlas.models import ResearchReport


def stratified_sample(reports: Sequence[ResearchReport], sample_size: int) -> list[ResearchReport]:
    """Deterministic round-robin sample so a large feed cannot hide smaller report types."""
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    groups: dict[str, dict[str, list[ResearchReport]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for report in reports:
        groups[report.report_type][
            report.org_name or "UNKNOWN_INSTITUTION"
        ].append(report)
    queues: dict[str, deque[deque[ResearchReport]]] = {}
    for report_type, institutions in groups.items():
        queues[report_type] = deque(
            deque(sorted(
                items,
                key=lambda item: (item.publish_date, item.resource_id),
                reverse=True,
            ))
            for _, items in sorted(institutions.items())
        )
    result: list[ResearchReport] = []
    while len(result) < sample_size:
        added = False
        for report_type in sorted(queues):
            institution_queues = queues[report_type]
            while institution_queues and not institution_queues[0]:
                institution_queues.popleft()
            if institution_queues:
                queue = institution_queues.popleft()
                result.append(queue.popleft())
                if queue:
                    institution_queues.append(queue)
                added = True
                if len(result) == sample_size:
                    break
        if not added:
            break
    return result

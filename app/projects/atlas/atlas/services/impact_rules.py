"""Impact rules engine — deterministic rules for supply chain impact calculation.

Per design doc §6.1 Step 3: Rules handle predictable cases,
LLM supplements complex/ambiguous scenarios.
"""
from __future__ import annotations

import logging
from typing import Any

from atlas.models.impact import ImpactItem

logger = logging.getLogger(__name__)

# ── Impact strength scoring (design doc §6.3) ─────────────────────────────

_BASE_SCORES = {"high": 3.0, "medium": 2.0, "low": 1.0}
_DISTANCE_DECAY = 0.7  # 30% decay per hop


def compute_strength_score(base_severity: str, hop: int, confidence: float = 1.0) -> float:
    """Compute impact strength score with distance decay.

    strength_score = base_score × distance_decay × confidence
    """
    base = _BASE_SCORES.get(base_severity, 2.0)
    decay = _DISTANCE_DECAY ** hop
    return base * decay * confidence


def score_to_label(score: float) -> str:
    """Map numeric score to label."""
    if score >= 2.0:
        return "high"
    elif score >= 1.0:
        return "medium"
    return "low"


# ── Rule definitions ───────────────────────────────────────────────────────

def apply_resource_price_rules(
    resource_name: str,
    price_direction: str,  # "up" or "down"
    affected_companies: list[dict],
    hop: int = 0,
) -> list[ImpactItem]:
    """Apply rules for resource price changes (design doc §6.1).

    - Upstream (extracts/produces resource) → positive if price up
    - Mid/downstream (depends/consumes resource) → negative if price up
    """
    impacts = []
    for company in affected_companies:
        rel_type = company.get("rel_type", "")
        name = company.get("name", "")
        ticker = company.get("ticker", "")
        confidence = company.get("confidence", 1.0)

        if rel_type in ("EXTRACTS_RESOURCE", "PRODUCES_RESOURCE"):
            direction = "positive" if price_direction == "up" else "negative"
            impact_type = "revenue"
            path = f"{resource_name}价格{'↑' if price_direction == 'up' else '↓'} → 矿产/生产利润{'↑' if direction == 'positive' else '↓'}"
        elif rel_type in ("DEPENDS_ON_RESOURCE", "CONSUMES_RESOURCE"):
            direction = "negative" if price_direction == "up" else "positive"
            impact_type = "cost"
            path = f"{resource_name}价格{'↑' if price_direction == 'up' else '↓'} → {name}成本{'↑' if direction == 'negative' else '↓'}"
        else:
            continue

        score = compute_strength_score("high", hop, confidence)
        impacts.append(ImpactItem(
            company=name,
            ticker=ticker,
            direction=direction,
            impact_type=impact_type,
            strength=score_to_label(score),
            strength_score=score,
            transmission_path=path,
            hop=hop,
            source="rule:resource_price",
        ))
    return impacts


def apply_supply_rules(
    resource_name: str,
    supply_status: str,  # "tight" or "oversupply"
    affected_companies: list[dict],
    hop: int = 0,
) -> list[ImpactItem]:
    """Apply rules for supply status changes.

    - Companies owning the resource → positive if tight
    - Companies depending on the resource → negative if tight
    """
    impacts = []
    for company in affected_companies:
        rel_type = company.get("rel_type", "")
        name = company.get("name", "")
        ticker = company.get("ticker", "")
        confidence = company.get("confidence", 1.0)

        if rel_type in ("EXTRACTS_RESOURCE", "PRODUCES_RESOURCE"):
            direction = "positive" if supply_status == "tight" else "negative"
            impact_type = "supply"
            path = f"{resource_name}供给{'紧张' if supply_status == 'tight' else '过剩'} → {name}供给优势{'↑' if direction == 'positive' else '↓'}"
        elif rel_type in ("DEPENDS_ON_RESOURCE", "CONSUMES_RESOURCE"):
            direction = "negative" if supply_status == "tight" else "positive"
            impact_type = "supply"
            path = f"{resource_name}供给{'紧张' if supply_status == 'tight' else '过剩'} → {name}供给风险{'↑' if direction == 'negative' else '↓'}"
        else:
            continue

        score = compute_strength_score("medium", hop, confidence)
        impacts.append(ImpactItem(
            company=name,
            ticker=ticker,
            direction=direction,
            impact_type=impact_type,
            strength=score_to_label(score),
            strength_score=score,
            transmission_path=path,
            hop=hop,
            source="rule:supply_status",
        ))
    return impacts


def apply_tariff_rules(
    policy_name: str,
    tariff_direction: str,  # "up" (increase) or "down" (decrease)
    affected_companies: list[dict],
    hop: int = 0,
) -> list[ImpactItem]:
    """Apply rules for tariff/trade policy changes.

    - Export-oriented companies → negative if tariff up
    - Domestic substitution companies → positive if tariff up
    """
    impacts = []
    for company in affected_companies:
        rel_type = company.get("rel_type", "")
        name = company.get("name", "")
        ticker = company.get("ticker", "")
        market = company.get("market", "")
        confidence = company.get("confidence", 1.0)

        if rel_type == "OPERATES_IN_MARKET" and "export" in market.lower():
            direction = "negative" if tariff_direction == "up" else "positive"
            impact_type = "revenue"
            path = f"{policy_name} → 关税{'↑' if tariff_direction == 'up' else '↓'} → {name}出口{'受阻' if direction == 'negative' else '受益'}"
        elif rel_type == "OPERATES_IN_MARKET" and "domestic" in market.lower():
            direction = "positive" if tariff_direction == "up" else "negative"
            impact_type = "demand"
            path = f"{policy_name} → 关税{'↑' if tariff_direction == 'up' else '↓'} → {name}国内替代需求{'↑' if direction == 'positive' else '↓'}"
        else:
            continue

        score = compute_strength_score("medium", hop, confidence)
        impacts.append(ImpactItem(
            company=name,
            ticker=ticker,
            direction=direction,
            impact_type=impact_type,
            strength=score_to_label(score),
            strength_score=score,
            transmission_path=path,
            hop=hop,
            source="rule:tariff",
        ))
    return impacts


def propagate_supply_chain(
    direct_impacts: list[ImpactItem],
    chain_neighbors: list[dict],
    max_hops: int = 3,
) -> list[ImpactItem]:
    """Propagate impacts along supply chain relationships with decay.

    For each directly impacted company, find its supply chain neighbors
    and compute indirect impacts with distance decay.
    """
    indirect = []
    seen = {item.company for item in direct_impacts}

    for neighbor in chain_neighbors:
        name = neighbor.get("company", "")
        if name in seen:
            continue
        seen.add(name)

        hop = neighbor.get("hop", 1)
        if hop > max_hops:
            continue

        via_rel = neighbor.get("via_relation", "")
        ticker = neighbor.get("ticker", "")

        # Infer direction based on relationship type
        # Default: same direction as the closest direct impact
        direction = "neutral"
        impact_type = "cost"

        if via_rel in ("SUPPLIER_OF",):
            direction = "negative"
            impact_type = "revenue"
        elif via_rel in ("CUSTOMER_OF",):
            direction = "negative"
            impact_type = "cost"

        score = compute_strength_score("medium", hop)
        indirect.append(ImpactItem(
            company=name,
            ticker=ticker,
            direction=direction,
            impact_type=impact_type,
            strength=score_to_label(score),
            strength_score=score,
            transmission_path=f"间接传导 (hop={hop}, via={via_rel})",
            hop=hop,
            source="rule:chain_propagation",
        ))

    return indirect


"""Tests for impact rules engine."""
import pytest

from atlas.services.impact_rules import (
    compute_strength_score,
    score_to_label,
    apply_resource_price_rules,
    apply_supply_rules,
    propagate_supply_chain,
)


class TestStrengthScoring:
    """Test impact strength score calculation."""

    def test_base_high_hop0(self):
        score = compute_strength_score("high", 0)
        assert score == 3.0

    def test_base_medium_hop0(self):
        score = compute_strength_score("medium", 0)
        assert score == 2.0

    def test_base_low_hop0(self):
        score = compute_strength_score("low", 0)
        assert score == 1.0

    def test_distance_decay_hop1(self):
        score = compute_strength_score("high", 1)
        assert abs(score - 3.0 * 0.7) < 0.01

    def test_distance_decay_hop2(self):
        score = compute_strength_score("high", 2)
        assert abs(score - 3.0 * 0.7 * 0.7) < 0.01

    def test_confidence_factor(self):
        score = compute_strength_score("high", 0, confidence=0.5)
        assert score == 1.5

    def test_combined_decay_and_confidence(self):
        score = compute_strength_score("high", 1, confidence=0.8)
        expected = 3.0 * 0.7 * 0.8
        assert abs(score - expected) < 0.01


class TestScoreToLabel:
    """Test numeric score to label mapping."""

    def test_high(self):
        assert score_to_label(2.5) == "high"
        assert score_to_label(2.0) == "high"

    def test_medium(self):
        assert score_to_label(1.5) == "medium"
        assert score_to_label(1.0) == "medium"

    def test_low(self):
        assert score_to_label(0.5) == "low"
        assert score_to_label(0.0) == "low"


class TestResourcePriceRules:
    """Test resource price change impact rules."""

    def test_upstream_positive_when_price_up(self):
        companies = [
            {"name": "天齐锂业", "ticker": "002466", "rel_type": "EXTRACTS_RESOURCE", "confidence": 1.0},
        ]
        impacts = apply_resource_price_rules("锂", "up", companies)
        assert len(impacts) == 1
        assert impacts[0].direction == "positive"
        assert impacts[0].impact_type == "revenue"

    def test_downstream_negative_when_price_up(self):
        companies = [
            {"name": "宁德时代", "ticker": "300750", "rel_type": "DEPENDS_ON_RESOURCE", "confidence": 1.0},
        ]
        impacts = apply_resource_price_rules("锂", "up", companies)
        assert len(impacts) == 1
        assert impacts[0].direction == "negative"
        assert impacts[0].impact_type == "cost"

    def test_upstream_negative_when_price_down(self):
        companies = [
            {"name": "天齐锂业", "ticker": "002466", "rel_type": "PRODUCES_RESOURCE", "confidence": 1.0},
        ]
        impacts = apply_resource_price_rules("锂", "down", companies)
        assert len(impacts) == 1
        assert impacts[0].direction == "negative"

    def test_unrelated_rel_type_skipped(self):
        companies = [
            {"name": "SomeCompany", "ticker": "", "rel_type": "COMPETITOR_OF", "confidence": 1.0},
        ]
        impacts = apply_resource_price_rules("锂", "up", companies)
        assert len(impacts) == 0

    def test_multiple_companies(self):
        companies = [
            {"name": "天齐锂业", "ticker": "002466", "rel_type": "EXTRACTS_RESOURCE", "confidence": 1.0},
            {"name": "宁德时代", "ticker": "300750", "rel_type": "CONSUMES_RESOURCE", "confidence": 1.0},
        ]
        impacts = apply_resource_price_rules("锂", "up", companies)
        assert len(impacts) == 2
        upstream = [i for i in impacts if i.company == "天齐锂业"][0]
        downstream = [i for i in impacts if i.company == "宁德时代"][0]
        assert upstream.direction == "positive"
        assert downstream.direction == "negative"


class TestSupplyRules:
    """Test supply status impact rules."""

    def test_tight_supply_positive_for_producers(self):
        companies = [
            {"name": "Producer", "ticker": "", "rel_type": "PRODUCES_RESOURCE", "confidence": 1.0},
        ]
        impacts = apply_supply_rules("锂", "tight", companies)
        assert len(impacts) == 1
        assert impacts[0].direction == "positive"

    def test_tight_supply_negative_for_consumers(self):
        companies = [
            {"name": "Consumer", "ticker": "", "rel_type": "CONSUMES_RESOURCE", "confidence": 1.0},
        ]
        impacts = apply_supply_rules("锂", "tight", companies)
        assert len(impacts) == 1
        assert impacts[0].direction == "negative"


class TestPropagateSupplyChain:
    """Test supply chain impact propagation."""

    def test_propagation_skips_direct(self):
        from atlas.models.impact import ImpactItem
        direct = [ImpactItem(company="A")]
        neighbors = [{"company": "A", "hop": 1, "via_relation": "SUPPLIER_OF", "ticker": ""}]
        indirect = propagate_supply_chain(direct, neighbors)
        assert len(indirect) == 0  # A is already in direct

    def test_propagation_includes_new(self):
        from atlas.models.impact import ImpactItem
        direct = [ImpactItem(company="A")]
        neighbors = [{"company": "B", "hop": 1, "via_relation": "SUPPLIER_OF", "ticker": ""}]
        indirect = propagate_supply_chain(direct, neighbors)
        assert len(indirect) == 1
        assert indirect[0].company == "B"

    def test_propagation_respects_max_hops(self):
        from atlas.models.impact import ImpactItem
        direct = [ImpactItem(company="A")]
        neighbors = [{"company": "B", "hop": 5, "via_relation": "SUPPLIER_OF", "ticker": ""}]
        indirect = propagate_supply_chain(direct, neighbors, max_hops=3)
        assert len(indirect) == 0


"""Tests for graph schema models — validation of LLM extraction output."""
import pytest
from pydantic import ValidationError

from atlas.models.graph_schema import (
    ExtractionResult,
    CompanyNode,
    Edge,
    Nodes,
    ExtractionMeta,
    SourceType,
    EventType,
)


class TestExtractionResult:
    def test_minimal_valid(self):
        result = ExtractionResult()
        assert result.meta.parser_version == "v5"
        assert len(result.edges) == 0

    def test_with_company_node(self):
        result = ExtractionResult(
            nodes=Nodes(companies=[
                CompanyNode(name="宁德时代", normalized_name="宁德时代", confidence=0.9)
            ])
        )
        assert len(result.nodes.companies) == 1
        assert result.nodes.companies[0].name == "宁德时代"

    def test_with_edge(self):
        result = ExtractionResult(
            edges=[Edge(
                type="supplier_of",
                from_node="A",
                to_node="B",
                confidence=0.8,
                **{"from": "A", "to": "B"},
            )]
        )
        assert len(result.edges) == 1

    def test_meta_source_type_validation(self):
        meta = ExtractionMeta(source_type=SourceType.EARNINGS)
        assert meta.source_type == "earnings"

    def test_event_type_values(self):
        assert EventType.PRICE_CHANGE == "price_change"
        assert EventType.OTHER == "other"
        assert EventType.MERGER_ACQUISITION == "merger_acquisition"

    def test_source_type_includes_new_types(self):
        assert SourceType.INDUSTRY == "industry"
        assert SourceType.POLICY == "policy"
        assert SourceType.MANUAL == "manual"


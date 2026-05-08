"""Tests for graph_builder — quality gate and batch merge logic."""
import pytest
from unittest.mock import AsyncMock, patch

from atlas.services.graph_builder import (
    _passes_quality_gate,
    _node_props,
    _resolve_label,
    _MERGE_KEY,
    _LABEL_MAP,
    _REL_TYPE_MAP,
)


class MockNode:
    def __init__(self, confidence=0.9, name="test", **kwargs):
        self.confidence = confidence
        self.name = name
        for k, v in kwargs.items():
            setattr(self, k, v)

    def model_dump(self, exclude_none=True):
        d = {"name": self.name, "confidence": self.confidence}
        return {k: v for k, v in d.items() if v is not None} if exclude_none else d


class TestQualityGate:
    @patch("atlas.services.graph_builder.get_config", return_value={"graph": {"low_confidence_threshold": 0.5}})
    def test_high_confidence_passes(self, _):
        node = MockNode(confidence=0.9)
        assert _passes_quality_gate(node) is True

    @patch("atlas.services.graph_builder.get_config", return_value={"graph": {"low_confidence_threshold": 0.5}})
    def test_low_confidence_fails(self, _):
        node = MockNode(confidence=0.3)
        assert _passes_quality_gate(node) is False

    @patch("atlas.services.graph_builder.get_config", return_value={"graph": {"low_confidence_threshold": 0.5}})
    def test_threshold_boundary_passes(self, _):
        node = MockNode(confidence=0.5)
        assert _passes_quality_gate(node) is True

    @patch("atlas.services.graph_builder.get_config", return_value={"graph": {}})  # Missing key uses default 0.5
    def test_default_threshold(self, _):
        node = MockNode(confidence=0.6)
        assert _passes_quality_gate(node) is True


class TestNodeProps:
    def test_basic_props(self):
        class N:
            def model_dump(self, **kw):
                return {"name": "test", "ticker": "123"}
        props = _node_props(N(), doc_id="doc1")
        assert props["name"] == "test"
        # source_doc_ids is a list that gets JSON-serialized by _node_props
        assert "doc1" in props["source_doc_ids"]

    def test_list_fields_serialized(self):
        class N:
            def model_dump(self, **kw):
                return {"name": "test", "products": ["A", "B"]}
        props = _node_props(N(), doc_id="")
        assert isinstance(props["products"], str)
        assert "A" in props["products"]

    def test_evidence_removed(self):
        class N:
            def model_dump(self, **kw):
                return {"name": "test", "evidence": "some text", "source": {}}
        props = _node_props(N())
        assert "evidence" not in props
        assert "source" not in props


class TestLabelMap:
    def test_all_labels_have_merge_keys(self):
        for field, label in _LABEL_MAP.items():
            assert label in _MERGE_KEY, f"Label {label} (from field {field}) missing merge key"

    def test_rel_type_map_uppercased(self):
        for key, val in _REL_TYPE_MAP.items():
            assert val == val.upper(), f"Relationship type {val} should be uppercase"


class TestResolveLabel:
    def test_resolves_company(self):
        from atlas.models.graph_schema import ExtractionResult, Nodes, CompanyNode
        result = ExtractionResult(
            nodes=Nodes(companies=[CompanyNode(name="Test", normalized_name="Test", confidence=0.9)])
        )
        assert _resolve_label("Test", result) == "Company"

    def test_returns_none_for_unknown(self):
        from atlas.models.graph_schema import ExtractionResult
        result = ExtractionResult()
        assert _resolve_label("Unknown", result) is None



"""Tests for phoenixa_client graph methods — mock HTTP layer."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from atlas.connectors import phoenixa_client


class MockResponse:
    """Mock httpx.Response."""
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def reset_client():
    phoenixa_client._client = None
    yield
    phoenixa_client._client = None


@pytest.fixture
def mock_client():
    client = AsyncMock()
    phoenixa_client._client = client
    return client


class TestGraphSearchNodes:
    @pytest.mark.asyncio
    async def test_returns_results(self, mock_client):
        mock_client.get = AsyncMock(return_value=MockResponse({
            "data": {"results": [{"props": {"name": "宁德时代"}, "label": "Company"}], "total": 1}
        }))
        results = await phoenixa_client.graph_search_nodes("宁德时代")
        assert len(results) == 1
        assert results[0]["props"]["name"] == "宁德时代"

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_client):
        mock_client.get = AsyncMock(return_value=MockResponse({"data": {"results": []}}))
        results = await phoenixa_client.graph_search_nodes("nonexistent")
        assert results == []


class TestRunCypher:
    @pytest.mark.asyncio
    async def test_returns_rows(self, mock_client):
        mock_client.post = AsyncMock(return_value=MockResponse({
            "data": [{"name": "A", "count": 5}]
        }))
        rows = await phoenixa_client.run_cypher("MATCH (n) RETURN n.name AS name, count(*) AS count")
        assert len(rows) == 1
        assert rows[0]["name"] == "A"

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_client):
        mock_client.post = AsyncMock(return_value=MockResponse({"data": []}))
        rows = await phoenixa_client.run_cypher("MATCH (n:Nothing) RETURN n")
        assert rows == []


class TestMergeNode:
    @pytest.mark.asyncio
    async def test_merge_single(self, mock_client):
        mock_client.post = AsyncMock(return_value=MockResponse({"data": {"affected": 1}}))
        result = await phoenixa_client.merge_node("Company", "normalized_name", "宁德时代", {"ticker": "300750"})
        assert result["affected"] == 1

    @pytest.mark.asyncio
    async def test_merge_batch(self, mock_client):
        mock_client.post = AsyncMock(return_value=MockResponse({"data": {"total_affected": 3, "count": 3}}))
        nodes = [
            {"label": "Company", "merge_key": "normalized_name", "merge_value": "A", "props": {}},
            {"label": "Company", "merge_key": "normalized_name", "merge_value": "B", "props": {}},
            {"label": "Product", "merge_key": "name", "merge_value": "C", "props": {}},
        ]
        result = await phoenixa_client.merge_nodes_batch(nodes)
        assert result["count"] == 3


class TestMergeEdge:
    @pytest.mark.asyncio
    async def test_merge_single(self, mock_client):
        mock_client.post = AsyncMock(return_value=MockResponse({"data": {"affected": 1}}))
        result = await phoenixa_client.merge_edge(
            "Company", "normalized_name", "A",
            "Company", "normalized_name", "B",
            "SUPPLIER_OF", {"confidence": 0.9},
        )
        assert result["affected"] == 1

    @pytest.mark.asyncio
    async def test_merge_batch(self, mock_client):
        mock_client.post = AsyncMock(return_value=MockResponse({"data": {"total_affected": 2, "count": 2}}))
        edges = [
            {"from_label": "Company", "from_key": "normalized_name", "from_value": "A",
             "to_label": "Company", "to_key": "normalized_name", "to_value": "B",
             "rel_type": "SUPPLIER_OF", "attrs": {}},
            {"from_label": "Company", "from_key": "normalized_name", "from_value": "B",
             "to_label": "Product", "to_key": "name", "to_value": "C",
             "rel_type": "PRODUCES", "attrs": {}},
        ]
        result = await phoenixa_client.merge_edges_batch(edges)
        assert result["count"] == 2


class TestGraphGetCompany:
    @pytest.mark.asyncio
    async def test_returns_company_data(self, mock_client):
        mock_client.get = AsyncMock(return_value=MockResponse({
            "data": {"company": {"name": "宁德时代"}, "relationships": []}
        }))
        result = await phoenixa_client.graph_get_company("宁德时代")
        assert result["company"]["name"] == "宁德时代"


class TestGraphGetStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self, mock_client):
        mock_client.get = AsyncMock(return_value=MockResponse({
            "data": {"total_nodes": 100, "total_edges": 200, "node_counts": {"Company": 50}}
        }))
        result = await phoenixa_client.graph_get_stats()
        assert result["total_nodes"] == 100
        assert result["node_counts"]["Company"] == 50


class TestGraphEnsureSchema:
    @pytest.mark.asyncio
    async def test_calls_endpoint(self, mock_client):
        mock_resp = MockResponse({"status": "ok"})
        mock_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        await phoenixa_client.graph_ensure_schema()
        mock_client.post.assert_called_once()


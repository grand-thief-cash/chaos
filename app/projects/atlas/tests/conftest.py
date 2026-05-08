"""Shared test fixtures for Atlas."""
import pytest
from unittest.mock import patch


_TEST_CONFIG = {
    "server": {"host": "0.0.0.0", "port": 18400},
    "neo4j": {
        "uri": "bolt://localhost:7687",
        "username": "neo4j",
        "password": "test",
        "database": "neo4j",
        "max_connection_pool_size": 10,
    },
    "llm": {
        "extraction_model": "test-model",
        "filter_model": "test-model",
        "summary_model": "test-model",
        "reasoning_model": "test-model",
        "api_key": "test-key",
        "api_base": "http://localhost:8000",
        "max_retries": 1,
        "request_timeout": 10,
        "batch_concurrency": 1,
    },
    "document": {
        "storage_dir": "/tmp/atlas-test-docs",
        "chunk_max_chars": 3000,
        "chunk_overlap_chars": 200,
    },
    "graph": {
        "company_merge_threshold": 0.85,
        "impact_max_hops": 3,
        "low_confidence_threshold": 0.5,
    },
    "pipeline": {
        "news_sources": [],
        "daily_max_news": 10,
        "daily_max_extraction": 5,
    },
    "minio": {
        "endpoint": "localhost:9000",
        "access_key": "test",
        "secret_key": "test",
        "secure": False,
        "bucket": "test-bucket",
    },
    "dept_services": {
        "cronjob": {"host": "127.0.0.1", "port": 19999},
        "phoenixA": {"host": "127.0.0.1", "port": 18085},
    },
    "taxonomy": {
        "doc_types": ["earnings", "research", "news"],
        "event_types": ["price_change", "supply_change", "other"],
    },
}


@pytest.fixture(autouse=True)
def mock_config():
    """Auto-mock get_config for all tests."""
    with patch("atlas.core.config.get_config", return_value=_TEST_CONFIG):
        yield _TEST_CONFIG


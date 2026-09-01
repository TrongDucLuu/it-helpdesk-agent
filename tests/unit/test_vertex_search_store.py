"""
Unit Tests for VertexAiSearchKnowledgeStore (VAIS-021 & VAIS-024).

Validates:
- Discovery Engine API integration with mock SearchServiceClient and DocumentServiceClient.
- Fail-Closed error handling (KnowledgeStoreUnavailableError on API failure).
- Governance date validation (effective_date, expiry_date) and tombstone (is_deleted) filtering.
- Relevance score normalization [0.0, 1.0].
- Full get_article_by_id lifecycle (found, not found, API error).
"""

import pytest
import datetime
from unittest.mock import MagicMock, patch
from it_helpdesk_agent.tools.enterprise_rag.vertex_search_store import (
    VertexAiSearchKnowledgeStore,
)
from it_helpdesk_agent.tools.enterprise_rag_mcp.knowledge_store import (
    KnowledgeStoreUnavailableError,
)
from it_helpdesk_agent.tools.enterprise_rag_mcp.rag_models import (
    SearchResult,
    KnowledgeArticle,
)


@pytest.fixture
def mock_clients():
    mock_search = MagicMock()
    mock_doc = MagicMock()
    return mock_search, mock_doc


@pytest.fixture
def store(mock_clients):
    mock_search, mock_doc = mock_clients
    return VertexAiSearchKnowledgeStore(
        project_id="test-project",
        location="global",
        data_store_id="test-datastore",
        search_client=mock_search,
        document_client=mock_doc,
    )


def test_search_success_with_snippet_and_rbac(store, mock_clients):
    mock_search, _ = mock_clients

    # Create mock result item
    mock_item = MagicMock()
    mock_item.model_scores = {"model": 0.88}
    mock_doc = MagicMock()
    mock_doc.id = "ERP-KB-001"
    mock_doc.struct_data = {
        "id": "ERP-KB-001",
        "system": "ERP",
        "title": "SAP PO Guide",
        "category": "Finance",
        "content": "Full ERP content for PO.",
        "source_uri": "docs/po.md",
        "keywords": ["sap", "po"],
        "owner": "erp@company.com",
        "effective_date": "2025-01-01",
        "expiry_date": None,
        "is_deleted": False,
        "chunk_id": "chunk-123",
        "parent_doc_id": "doc-456",
        "section_hierarchy": {"h1": "SAP", "h2": "PO", "h3": "Guide"},
    }
    mock_doc.derived_struct_data = {
        "snippets": [{"snippet": "Quick SAP PO snippet..."}]
    }
    mock_item.document = mock_doc

    mock_response = MagicMock()
    mock_response.results = [mock_item]
    mock_search.search.return_value = mock_response

    results = store.search(
        query="SAP PO issue",
        system="ERP",
        limit=2,
        allowed_systems=["ERP", "HRM"],
    )

    assert len(results) == 1
    res = results[0]
    assert isinstance(res, SearchResult)
    assert res.article_id == "ERP-KB-001"
    assert res.system == "ERP"
    assert "Quick SAP PO snippet" in res.snippet
    assert res.relevance_score == 0.88
    assert res.chunk_id == "chunk-123"
    assert res.parent_doc_id == "doc-456"
    assert res.section_hierarchy.h1 == "SAP"

    # Verify search call had system filter
    call_args, call_kwargs = mock_search.search.call_args
    req = call_kwargs.get("request")
    if req:
        assert 'system: ANY("ERP")' in req.filter
    else:
        assert 'system: ANY("ERP")' in call_kwargs.get("filter", "")


def test_search_empty_query_returns_empty_list(store):
    assert store.search("") == []
    assert store.search("   ") == []


def test_search_api_failure_raises_fail_closed_error(store, mock_clients):
    mock_search, _ = mock_clients
    mock_search.search.side_effect = Exception("Discovery Engine Connection Timeout 504")

    with pytest.raises(KnowledgeStoreUnavailableError) as exc_info:
        store.search("SAP issue", allowed_systems=["ERP"])

    assert "Agent Search gặp sự cố" in str(exc_info.value) or "504" in str(exc_info.value)


def test_governance_dates_and_tombstone_filtering(store, mock_clients):
    """VAIS-024: Verifies expired, future effective, and deleted articles are filtered out."""
    mock_search, _ = mock_clients

    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=1)).isoformat()
    last_year = (today - datetime.timedelta(days=365)).isoformat()
    tomorrow = (today + datetime.timedelta(days=1)).isoformat()
    next_year = (today + datetime.timedelta(days=365)).isoformat()

    # 1. Valid Active Article
    doc_valid = MagicMock()
    doc_valid.id = "ERP-KB-VALID"
    doc_valid.struct_data = {
        "id": "ERP-KB-VALID", "system": "ERP", "title": "Valid Doc",
        "content": "Valid", "effective_date": last_year, "expiry_date": next_year, "is_deleted": False
    }
    doc_valid.derived_struct_data = {}

    # 2. Expired Article (expiry_date in the past)
    doc_expired = MagicMock()
    doc_expired.id = "ERP-KB-EXPIRED"
    doc_expired.struct_data = {
        "id": "ERP-KB-EXPIRED", "system": "ERP", "title": "Expired Doc",
        "content": "Expired", "effective_date": last_year, "expiry_date": yesterday, "is_deleted": False
    }
    doc_expired.derived_struct_data = {}

    # 3. Future Article (effective_date in the future)
    doc_future = MagicMock()
    doc_future.id = "ERP-KB-FUTURE"
    doc_future.struct_data = {
        "id": "ERP-KB-FUTURE", "system": "ERP", "title": "Future Doc",
        "content": "Future", "effective_date": tomorrow, "expiry_date": next_year, "is_deleted": False
    }
    doc_future.derived_struct_data = {}

    # 4. Tombstone Article (is_deleted = True)
    doc_deleted = MagicMock()
    doc_deleted.id = "ERP-KB-DELETED"
    doc_deleted.struct_data = {
        "id": "ERP-KB-DELETED", "system": "ERP", "title": "Deleted Doc",
        "content": "Deleted", "effective_date": last_year, "expiry_date": next_year, "is_deleted": True
    }
    doc_deleted.derived_struct_data = {}

    mock_items = []
    for doc in [doc_valid, doc_expired, doc_future, doc_deleted]:
        item = MagicMock()
        item.document = doc
        mock_items.append(item)

    mock_response = MagicMock()
    mock_response.results = mock_items
    mock_search.search.return_value = mock_response

    results = store.search("test query", system="ERP", limit=10, allowed_systems=["ERP"])

    assert len(results) == 1
    assert results[0].article_id == "ERP-KB-VALID"


def test_get_article_by_id_found(store, mock_clients):
    _, mock_doc_client = mock_clients

    mock_doc = MagicMock()
    mock_doc.id = "ERP-KB-001"
    mock_doc.struct_data = {
        "id": "ERP-KB-001",
        "system": "ERP",
        "title": "SAP Manual",
        "category": "Finance",
        "content": "Detailed full manual for SAP.",
        "keywords": ["sap", "manual"],
        "source_uri": "docs/sap.md",
        "owner": "admin@company.com",
        "effective_date": "2025-01-01",
        "expiry_date": None,
        "is_deleted": False,
        "section_hierarchy": {"h1": "SAP", "h2": "Guide", "h3": "Overview"},
    }
    mock_doc_client.get_document.return_value = mock_doc

    article = store.get_article_by_id("ERP-KB-001")
    assert article is not None
    assert isinstance(article, KnowledgeArticle)
    assert article.id == "ERP-KB-001"
    assert article.system == "ERP"
    assert article.title == "SAP Manual"
    assert article.section_hierarchy.h1 == "SAP"


def test_get_article_by_id_not_found_returns_none(store, mock_clients):
    _, mock_doc_client = mock_clients
    mock_doc_client.get_document.side_effect = Exception("404 Document not found in data store")

    article = store.get_article_by_id("NONEXISTENT-999")
    assert article is None


def test_get_article_by_id_api_failure_raises_error(store, mock_clients):
    _, mock_doc_client = mock_clients
    mock_doc_client.get_document.side_effect = Exception("500 Internal Discovery Engine Crash")

    with pytest.raises(KnowledgeStoreUnavailableError) as exc_info:
        store.get_article_by_id("ERP-KB-001")

    assert "DocumentService thất bại" in str(exc_info.value)

"""
Vertex AI Search (Agent Search) Knowledge Store Adapter.

Integrates with Google Cloud Discovery Engine SearchServiceClient and DocumentServiceClient
to deliver enterprise search with Fail-Closed RBAC, Governance Date filtering, and Tombstone exclusion.

Google Cloud Official Documentation:
- Discovery Engine API Reference:
  https://cloud.google.com/python/docs/reference/discoveryengine/latest
- SearchServiceClient:
  https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.services.search_service.SearchServiceClient
- DocumentServiceClient:
  https://cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.services.document_service.DocumentServiceClient
- Filter Search Metadata:
  https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
- Preview Search Results / Snippets:
  https://cloud.google.com/generative-ai-app-builder/docs/preview-search-results
"""

import os
import logging
import datetime
from typing import Optional, Any

try:
    from google.cloud import discoveryengine_v1
    from google.api_core.exceptions import GoogleAPICallError, NotFound
except ImportError:
    discoveryengine_v1 = None  # type: ignore
    GoogleAPICallError = Exception  # type: ignore
    NotFound = Exception  # type: ignore

try:
    from it_helpdesk_agent.tools.enterprise_rag_mcp.rag_models import (
        KnowledgeArticle,
        SearchResult,
        SectionHierarchy,
    )
    from it_helpdesk_agent.tools.enterprise_rag_mcp.knowledge_store import (
        BaseKnowledgeStore,
        KnowledgeStoreUnavailableError,
        wrap_retrieved_document,
    )
    from it_helpdesk_agent.tools.enterprise_rag.filter_builder import build_system_filter
except ImportError:
    from tools.enterprise_rag_mcp.rag_models import (
        KnowledgeArticle,
        SearchResult,
        SectionHierarchy,
    )
    from tools.enterprise_rag_mcp.knowledge_store import (
        BaseKnowledgeStore,
        KnowledgeStoreUnavailableError,
        wrap_retrieved_document,
    )
    from tools.enterprise_rag.filter_builder import build_system_filter

logger = logging.getLogger(__name__)


def _parse_iso_date(date_str: Optional[str]) -> Optional[datetime.date]:
    """Safely parses YYYY-MM-DD date strings."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        clean = date_str.strip()[:10]
        return datetime.date.fromisoformat(clean)
    except Exception:
        return None


class VertexAiSearchKnowledgeStore(BaseKnowledgeStore):
    """
    Knowledge store adapter for Google Cloud Vertex AI Search (Agent Search / Discovery Engine).
    
    Provides:
    - Pre-search RBAC filtering via build_system_filter.
    - Post-retrieval Governance lifecycle validation (effective/expiry dates) and tombstone checks.
    - Unified SearchResult schema parity with relevance_score normalized to [0.0, 1.0].
    - Fail-Closed resilience (raises KnowledgeStoreUnavailableError on backend outage).
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        data_store_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        serving_config_id: Optional[str] = None,
        search_client: Optional[Any] = None,
        document_client: Optional[Any] = None,
    ):
        self.project_id = project_id or os.getenv("DISCOVERY_ENGINE_PROJECT_ID") or os.getenv("DATA_STORE_PROJECT_ID") or os.getenv("PROJECT_ID") or os.getenv("GCP_PROJECT_ID")
        self.location = location or os.getenv("DISCOVERY_ENGINE_LOCATION") or os.getenv("LOCATION", "global")
        self.data_store_id = data_store_id or os.getenv("DISCOVERY_ENGINE_DATA_STORE_ID") or os.getenv("DATA_STORE_ID")
        self.collection_id = collection_id or os.getenv("DISCOVERY_ENGINE_COLLECTION_ID") or os.getenv("COLLECTION_ID", "default_collection")
        self.serving_config_id = serving_config_id or os.getenv("DISCOVERY_ENGINE_SERVING_CONFIG_ID") or os.getenv("SERVING_CONFIG_ID", "default_search")

        self._search_client = search_client
        self._document_client = document_client

    @property
    def search_client(self) -> Any:
        if self._search_client is None:
            if discoveryengine_v1 is None:
                raise KnowledgeStoreUnavailableError("google-cloud-discoveryengine package is not installed.")
            try:
                self._search_client = discoveryengine_v1.SearchServiceClient()
            except Exception as e:
                logger.error("Failed to initialize Discovery Engine SearchServiceClient: %s", e)
                raise KnowledgeStoreUnavailableError(f"Không thể khởi tạo Discovery Engine SearchServiceClient: {e}") from e
        return self._search_client

    @property
    def document_client(self) -> Any:
        if self._document_client is None:
            if discoveryengine_v1 is None:
                raise KnowledgeStoreUnavailableError("google-cloud-discoveryengine package is not installed.")
            try:
                self._document_client = discoveryengine_v1.DocumentServiceClient()
            except Exception as e:
                logger.error("Failed to initialize Discovery Engine DocumentServiceClient: %s", e)
                raise KnowledgeStoreUnavailableError(f"Không thể khởi tạo Discovery Engine DocumentServiceClient: {e}") from e
        return self._document_client

    def _get_serving_config_path(self) -> str:
        """Builds full resource name for the serving config."""
        if not self.project_id or not self.data_store_id:
            raise KnowledgeStoreUnavailableError(
                "Thiếu cấu hình Discovery Engine: PROJECT_ID hoặc DATA_STORE_ID chưa được thiết lập."
            )
        return (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/collections/{self.collection_id}/dataStores/{self.data_store_id}"
            f"/servingConfigs/{self.serving_config_id}"
        )

    def _get_document_path(self, document_id: str) -> str:
        """Builds full resource name for a document."""
        if not self.project_id or not self.data_store_id:
            raise KnowledgeStoreUnavailableError(
                "Thiếu cấu hình Discovery Engine: PROJECT_ID hoặc DATA_STORE_ID chưa được thiết lập."
            )
        return (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/collections/{self.collection_id}/dataStores/{self.data_store_id}"
            f"/branches/0/documents/{document_id}"
        )

    def search(
        self,
        query: str,
        system: str = "ALL",
        limit: int = 3,
        allowed_systems: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """
        Executes search against Discovery Engine with RBAC filter, governance checks, and score normalization.
        """
        if not query or not query.strip():
            return []

        # 1. Build secure metadata filter expression (Fail-Closed)
        filter_expr = build_system_filter(
            allowed_systems=allowed_systems,
            target_system=system,
            field_name="system",
        )

        serving_config_path = self._get_serving_config_path()

        # 2. Configure request with SnippetSpec & ExtractiveContentSpec
        # Official Doc: https://cloud.google.com/generative-ai-app-builder/docs/preview-search-results
        snippet_spec = None
        extractive_spec = None
        if discoveryengine_v1:
            try:
                snippet_spec = discoveryengine_v1.SearchRequest.ContentSearchSpec.SnippetSpec(
                    return_snippet=True
                )
                extractive_spec = discoveryengine_v1.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                    max_extractive_answer_count=1
                )
                content_search_spec = discoveryengine_v1.SearchRequest.ContentSearchSpec(
                    snippet_spec=snippet_spec,
                    extractive_content_spec=extractive_spec,
                )
            except Exception:
                content_search_spec = None
        else:
            content_search_spec = None

        try:
            if discoveryengine_v1:
                request = discoveryengine_v1.SearchRequest(
                    serving_config=serving_config_path,
                    query=query.strip(),
                    page_size=limit * 2,  # Fetch extra to accommodate governance date post-filtering
                    filter=filter_expr,
                    content_search_spec=content_search_spec,
                )
                response = self.search_client.search(request=request)
            else:
                # Mock or duck-typed client call
                response = self.search_client.search(
                    serving_config=serving_config_path,
                    query=query.strip(),
                    page_size=limit * 2,
                    filter=filter_expr,
                )
        except Exception as e:
            logger.error("Vertex AI Search query failed: %s. Raising KnowledgeStoreUnavailableError.", e)
            raise KnowledgeStoreUnavailableError(f"Dịch vụ Agent Search gặp sự cố: {e}") from e

        results: list[SearchResult] = []
        today = datetime.date.today()

        raw_results = getattr(response, "results", response)
        for item in raw_results:
            doc = getattr(item, "document", item)
            doc_id = getattr(doc, "id", "") or ""
            
            struct_data = getattr(doc, "struct_data", {})
            if hasattr(struct_data, "items"):
                struct_data = dict(struct_data)
            elif not isinstance(struct_data, dict):
                struct_data = {}

            derived_data = getattr(doc, "derived_struct_data", {})
            if hasattr(derived_data, "items"):
                derived_data = dict(derived_data)
            elif not isinstance(derived_data, dict):
                derived_data = {}

            # Metadata extraction
            art_id = struct_data.get("id") or doc_id or "UNKNOWN"
            art_sys = (struct_data.get("system") or "UNKNOWN").upper().strip()
            art_title = struct_data.get("title") or ""
            source_uri = struct_data.get("source_uri")
            category = struct_data.get("category")
            keywords = struct_data.get("keywords") or []
            if not isinstance(keywords, list):
                keywords = [str(keywords)]
            owner = struct_data.get("owner")
            effective_date_str = struct_data.get("effective_date")
            expiry_date_str = struct_data.get("expiry_date")
            is_deleted = bool(struct_data.get("is_deleted", False))
            chunk_id = struct_data.get("chunk_id")
            parent_doc_id = struct_data.get("parent_doc_id")

            # --- VAIS-024: Governance Date & Tombstone Filter ---
            # Decision Rationale: While Discovery Engine supports basic metadata filters, client-side
            # date verification ensures resilient date-boundary enforcement across mixed date schemas.
            # Official Doc: https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
            if is_deleted:
                logger.debug("Document %s skipped (tombstone / is_deleted=True)", art_id)
                continue

            eff_date = _parse_iso_date(effective_date_str)
            if eff_date and eff_date > today:
                logger.debug("Document %s skipped (effective_date %s is in future)", art_id, eff_date)
                continue

            exp_date = _parse_iso_date(expiry_date_str)
            if exp_date and exp_date <= today:
                logger.debug("Document %s skipped (expired on %s)", art_id, exp_date)
                continue

            # Content & Snippet Resolution
            raw_snippet = ""
            snippets_list = derived_data.get("snippets") or []
            if snippets_list and isinstance(snippets_list, list) and len(snippets_list) > 0:
                first_snip = snippets_list[0]
                if isinstance(first_snip, dict):
                    raw_snippet = first_snip.get("snippet", "")
                elif hasattr(first_snip, "snippet"):
                    raw_snippet = getattr(first_snip, "snippet", "")

            if not raw_snippet:
                extractive_answers = derived_data.get("extractive_answers") or []
                if extractive_answers and isinstance(extractive_answers, list) and len(extractive_answers) > 0:
                    first_ans = extractive_answers[0]
                    if isinstance(first_ans, dict):
                        raw_snippet = first_ans.get("content", "")
                    elif hasattr(first_ans, "content"):
                        raw_snippet = getattr(first_ans, "content", "")

            if not raw_snippet:
                raw_snippet = struct_data.get("content", "")

            is_truncated = len(raw_snippet) > 200
            truncated_snip = raw_snippet[:200].strip() + "..." if is_truncated else raw_snippet.strip()
            snippet = wrap_retrieved_document(
                content=truncated_snip,
                doc_id=art_id,
                system=art_sys,
                title=art_title,
            )

            # Relevance Score Normalization to [0.0, 1.0]
            raw_score = 1.0
            if hasattr(item, "model_scores") and item.model_scores:
                try:
                    raw_score = float(list(item.model_scores.values())[0])
                except Exception:
                    raw_score = 1.0
            elif hasattr(item, "relevance_score"):
                try:
                    raw_score = float(item.relevance_score)
                except Exception:
                    raw_score = 1.0

            normalized_score = round(max(0.0, min(1.0, raw_score)), 4)

            # Section Hierarchy
            raw_hier = struct_data.get("section_hierarchy")
            sec_hier = None
            context_path = None
            if raw_hier and isinstance(raw_hier, dict):
                sec_hier = SectionHierarchy(
                    h1=raw_hier.get("h1"),
                    h2=raw_hier.get("h2"),
                    h3=raw_hier.get("h3"),
                )
                context_path = sec_hier.format_path()
            else:
                context_path = f"{art_sys} > {category or 'General'} > {art_title}"

            results.append(
                SearchResult(
                    article_id=art_id,
                    system=art_sys,
                    title=art_title,
                    snippet=snippet,
                    relevance_score=normalized_score,
                    section_hierarchy=sec_hier,
                    context_path=context_path,
                    source_uri=source_uri,
                    category=category,
                    keywords=keywords,
                    owner=owner,
                    effective_date=effective_date_str,
                    expiry_date=expiry_date_str,
                    is_deleted=is_deleted,
                    is_truncated=is_truncated,
                    chunk_id=chunk_id,
                    parent_doc_id=parent_doc_id,
                )
            )

            if len(results) >= limit:
                break

        return results

    def get_article_by_id(self, article_id: str) -> Optional[KnowledgeArticle]:
        """
        Retrieves full knowledge article by ID from DocumentServiceClient or SearchServiceClient.
        If the document is split across multiple chunks, aggregates and sorts all chunks by chunk_index
        to reconstruct and return the complete, unified document (VAIS-051).
        Returns None if not found, or raises KnowledgeStoreUnavailableError on backend failure.
        """
        if not article_id or not article_id.strip():
            return None

        clean_id = article_id.strip()
        doc_name = self._get_document_path(clean_id)

        doc = None
        try:
            if discoveryengine_v1:
                request = discoveryengine_v1.GetDocumentRequest(name=doc_name)
                doc = self.document_client.get_document(request=request)
            else:
                doc = self.document_client.get_document(name=doc_name)
        except Exception as e:
            err_str = str(e).lower()
            if not ("not found" in err_str or "404" in err_str or (NotFound and isinstance(e, NotFound))):
                logger.error("Discovery Engine get_document failed for %s: %s", clean_id, e)
                raise KnowledgeStoreUnavailableError(f"Truy vấn DocumentService thất bại: {e}") from e
            logger.info("Document %s not found directly via get_document, attempting parent/chunk search.", clean_id)

        # Helper to extract struct_data
        def _get_struct(d) -> dict:
            sd = getattr(d, "struct_data", {})
            if hasattr(sd, "items"):
                return dict(sd)
            return sd if isinstance(sd, dict) else {}

        struct_data = _get_struct(doc) if doc else {}
        parent_doc_id = struct_data.get("parent_doc_id") or clean_id
        chunk_count = int(struct_data.get("chunk_count", 1) or 1)

        # If doc was not found directly or it's part of a multi-chunk document, query for all chunks
        if not doc or chunk_count > 1 or struct_data.get("parent_doc_id"):
            try:
                serving_config_path = self._get_serving_config_path()
                chunk_filter = f'parent_doc_id: ANY("{parent_doc_id}")'
                
                if discoveryengine_v1:
                    req = discoveryengine_v1.SearchRequest(
                        serving_config=serving_config_path,
                        query="",
                        page_size=50,
                        filter=chunk_filter,
                    )
                    resp = self.search_client.search(request=req)
                else:
                    resp = self.search_client.search(
                        serving_config=serving_config_path,
                        query="",
                        page_size=50,
                        filter=chunk_filter,
                    )

                raw_results = getattr(resp, "results", resp) or []
                matching_docs = []
                for item in raw_results:
                    sub_doc = getattr(item, "document", item)
                    sub_sd = _get_struct(sub_doc)
                    if sub_sd.get("parent_doc_id") == parent_doc_id or getattr(sub_doc, "id", "") == parent_doc_id:
                        matching_docs.append((sub_sd, getattr(sub_doc, "id", "")))

                if matching_docs:
                    # Sort chunks by chunk_index
                    matching_docs.sort(key=lambda x: int(x[0].get("chunk_index", 0) or 0))
                    primary_sd, primary_id = matching_docs[0]
                    full_content = "\n\n".join(sd.get("content", "").strip() for sd, _ in matching_docs if sd.get("content"))

                    raw_hier = primary_sd.get("section_hierarchy")
                    sec_hier = None
                    if raw_hier and isinstance(raw_hier, dict):
                        sec_hier = SectionHierarchy(
                            h1=raw_hier.get("h1"),
                            h2=raw_hier.get("h2"),
                            h3=raw_hier.get("h3"),
                        )

                    keywords = primary_sd.get("keywords") or []
                    if not isinstance(keywords, list):
                        keywords = [str(keywords)]

                    return KnowledgeArticle(
                        id=parent_doc_id,
                        system=(primary_sd.get("system") or "UNKNOWN").upper().strip(),
                        title=primary_sd.get("title") or "",
                        category=primary_sd.get("category") or "General",
                        content=full_content,
                        keywords=keywords,
                        section_hierarchy=sec_hier,
                        source_uri=primary_sd.get("source_uri"),
                        owner=primary_sd.get("owner"),
                        effective_date=primary_sd.get("effective_date"),
                        expiry_date=primary_sd.get("expiry_date"),
                        is_deleted=bool(primary_sd.get("is_deleted", False)),
                    )
            except Exception as e:
                logger.debug("Failed chunk reassembly search for parent %s: %s", parent_doc_id, e)
                if not doc:
                    return None

        if not doc:
            return None

        raw_hier = struct_data.get("section_hierarchy")
        sec_hier = None
        if raw_hier and isinstance(raw_hier, dict):
            sec_hier = SectionHierarchy(
                h1=raw_hier.get("h1"),
                h2=raw_hier.get("h2"),
                h3=raw_hier.get("h3"),
            )

        keywords = struct_data.get("keywords") or []
        if not isinstance(keywords, list):
            keywords = [str(keywords)]

        return KnowledgeArticle(
            id=struct_data.get("id") or getattr(doc, "id", clean_id),
            system=(struct_data.get("system") or "UNKNOWN").upper().strip(),
            title=struct_data.get("title") or "",
            category=struct_data.get("category") or "General",
            content=struct_data.get("content") or "",
            keywords=keywords,
            section_hierarchy=sec_hier,
            source_uri=struct_data.get("source_uri"),
            owner=struct_data.get("owner"),
            effective_date=struct_data.get("effective_date"),
            expiry_date=struct_data.get("expiry_date"),
            is_deleted=bool(struct_data.get("is_deleted", False)),
        )

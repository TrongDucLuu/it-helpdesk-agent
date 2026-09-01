#!/usr/bin/env python3
"""
Spike & Smoke Test for Vertex AI Search (Agent Search / Discovery Engine)

Official Documentation References:
- Discovery Engine Python SDK: https://cloud.google.com/generative-ai-app-builder/docs/locations
- SearchServiceClient & SearchRequest: https://cloud.google.com/generative-ai-app-builder/docs/snippets
- Filter Syntax: https://cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
- Document Import: https://cloud.google.com/generative-ai-app-builder/docs/import-documents
"""

import argparse
import sys
from typing import Optional


def run_spike(
    project_id: str,
    location: str,
    data_store_id: str,
    query: str = "chính sách nghỉ phép",
    filter_expr: Optional[str] = 'system: ANY("HRM")',
) -> int:
    print("=" * 60)
    print("VERTEX AI SEARCH (AGENT SEARCH) SPIKE VERIFICATION")
    print("=" * 60)
    print(f"Project ID     : {project_id}")
    print(f"Location       : {location}")
    print(f"Data Store ID  : {data_store_id}")
    print(f"Query          : {query}")
    print(f"Filter Expr    : {filter_expr}")
    print("-" * 60)

    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import discoveryengine_v1 as discoveryengine
    except ImportError:
        print("[ERROR] google-cloud-discoveryengine is not installed.")
        print("Please install via: pip install google-cloud-discoveryengine>=0.13.0")
        return 1

    try:
        client_options = (
            ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
            if location != "global"
            else None
        )
        client = discoveryengine.SearchServiceClient(client_options=client_options)

        serving_config = client.serving_config_path(
            project=project_id,
            location=location,
            data_store=data_store_id,
            serving_config="default_search",
        )

        content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
            snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True
            ),
            summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=3,
                include_citations=True,
            ),
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=5,
            filter=filter_expr,
            content_search_spec=content_search_spec,
        )

        print("[INFO] Sending SearchRequest to Discovery Engine...")
        response = client.search(request)

        print("\n[SUCCESS] Received SearchResponse:")
        result_count = 0
        for result in response:
            result_count += 1
            doc = result.document
            doc_id = result.id or getattr(doc, "id", "N/A")
            struct_data = getattr(doc, "struct_data", {}) or {}
            title = struct_data.get("title", getattr(doc, "name", "Untitled"))
            snippets = getattr(doc, "derived_struct_data", {}).get("snippets", [])
            snippet_text = snippets[0].get("snippet", "") if snippets else "No snippet"

            print(f"[{result_count}] ID: {doc_id}")
            print(f"    Title  : {title}")
            print(f"    Snippet: {snippet_text[:120]}...")

        print(f"\nTotal results retrieved: {result_count}")
        return 0

    except Exception as exc:
        print(f"[FATAL] Discovery Engine API call failed: {exc}")
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Vertex AI Search API Spike Runner")
    parser.add_argument("--project-id", type=str, default="it-helpdesk-staging", help="GCP Project ID")
    parser.add_argument("--location", type=str, default="asia-southeast1", help="GCP Region (e.g., asia-southeast1, global)")
    parser.add_argument("--data-store-id", type=str, default="enterprise-knowledge-store", help="Discovery Engine Data Store ID")
    parser.add_argument("--query", type=str, default="hướng dẫn quy trình nghỉ phép", help="Search query")
    parser.add_argument("--filter", type=str, default='system: ANY("HRM")', help="Metadata filter expression")
    parser.add_argument("--check-imports-only", action="store_true", help="Only verify imports and syntax")

    args = parser.parse_args()

    if args.check_imports_only:
        print("[INFO] Checking SDK imports and class availability...")
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import discoveryengine_v1 as discoveryengine
            assert hasattr(discoveryengine, "SearchServiceClient")
            assert hasattr(discoveryengine, "DocumentServiceClient")
            assert hasattr(discoveryengine, "DataStoreServiceClient")
            assert hasattr(discoveryengine, "SearchRequest")
            print("[SUCCESS] google-cloud-discoveryengine classes verified.")
            return 0
        except Exception as e:
            print(f"[ERROR] Import check failed: {e}")
            return 1

    return run_spike(
        project_id=args.project_id,
        location=args.location,
        data_store_id=args.data_store_id,
        query=args.query,
        filter_expr=args.filter,
    )


if __name__ == "__main__":
    sys.exit(main())

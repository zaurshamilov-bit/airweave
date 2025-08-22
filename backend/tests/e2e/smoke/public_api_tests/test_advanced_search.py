"""
Advanced search feature tests for the public API.

This module contains comprehensive tests for all new search features including:
- Query expansion strategies
- Query interpretation (NL filter extraction)
- Reranking
- Recency bias
- Search methods (hybrid, neural, keyword)
- Qdrant filters
- Score threshold
- Pagination
- Edge cases
"""

import json
import requests


def test_advanced_search_features(api_url: str, headers: dict, collection_id: str) -> None:
    """Test advanced search features including query expansion, interpretation, reranking, etc.

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        collection_id: The readable_id of the collection to search
    """
    print("\n🔬 Testing Advanced Search Features")

    # TEST 1: Query Expansion Strategies
    test_query_expansion_strategies(api_url, headers, collection_id)

    # TEST 2: Query Interpretation (Natural Language Filter Extraction)
    test_query_interpretation(api_url, headers, collection_id)

    # TEST 3: Reranking
    test_reranking(api_url, headers, collection_id)

    # TEST 4: Recency Bias
    test_recency_bias(api_url, headers, collection_id)

    # TEST 5: Search Methods (hybrid, neural, keyword)
    test_search_methods(api_url, headers, collection_id)

    # TEST 6: Advanced Filtering with Qdrant Filters
    test_qdrant_filters(api_url, headers, collection_id)

    # TEST 7: Score Threshold
    test_score_threshold(api_url, headers, collection_id)

    # TEST 8: Pagination
    test_pagination(api_url, headers, collection_id)

    # TEST 9: Edge Cases
    test_edge_cases(api_url, headers, collection_id)

    print("\n✅ Advanced search features test completed")


def test_query_expansion_strategies(api_url: str, headers: dict, collection_id: str) -> None:
    """Test different query expansion strategies."""
    print("\n  📝 Testing Query Expansion Strategies")

    strategies = [
        ("no_expansion", "invoice payment"),
        ("auto", "customer billing issues"),
        ("llm", "financial transactions"),
    ]

    for strategy, query in strategies:
        print(f"\n    Testing {strategy} strategy with query: '{query}'")

        # Use POST endpoint for advanced features
        request_body = {
            "query": query,
            "expansion_strategy": strategy,
            "limit": 5,
            "response_type": "raw",
        }

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=request_body,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json()
            num_results = len(results.get("results", []))
            print(f"      ✓ {strategy}: {num_results} results returned")

            # AUTO and LLM should generally return more diverse results
            if strategy in ["auto", "llm"] and num_results > 0:
                # Check if results have varied scores (indicating query expansion worked)
                scores = [r.get("score", 0) for r in results.get("results", [])]
                score_variance = max(scores) - min(scores) if scores else 0
                print(f"      Score variance: {score_variance:.4f}")
        else:
            print(f"      ⚠️  {strategy} returned {response.status_code}: {response.text[:100]}")


def test_query_interpretation(api_url: str, headers: dict, collection_id: str) -> None:
    """Test natural language filter extraction."""
    print("\n  🧠 Testing Query Interpretation")

    # Test queries that should extract filters
    test_cases = [
        {
            "query": "invoices from Lufthansa in the last month",
            "enable_query_interpretation": True,
            "description": "Should extract company and time filters",
        },
        {
            "query": "invoices from Lufthansa in the last month",
            "enable_query_interpretation": False,
            "description": "Should NOT extract filters (disabled)",
        },
        {
            "query": "recent payment issues",
            "enable_query_interpretation": True,
            "description": "Should extract recency filter",
        },
    ]

    for test_case in test_cases:
        print(f"\n    Test: {test_case['description']}")
        print(f"    Query: '{test_case['query']}'")

        request_body = {
            "query": test_case["query"],
            "enable_query_interpretation": test_case["enable_query_interpretation"],
            "limit": 5,
            "response_type": "raw",
        }

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=request_body,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json()
            num_results = len(results.get("results", []))
            status = results.get("status", "")
            print(
                f"      ✓ Interpretation {'ON' if test_case['enable_query_interpretation'] else 'OFF'}: "
            )
            print(f"        {num_results} results, status: {status}")

            # When interpretation is on, results should be more focused
            if num_results > 0 and test_case["enable_query_interpretation"]:
                # Check if Lufthansa appears in results when searching for it
                if "Lufthansa" in test_case["query"]:
                    lufthansa_found = any(
                        "lufthansa" in json.dumps(r.get("payload", {})).lower()
                        for r in results.get("results", [])
                    )
                    if lufthansa_found:
                        print("        ✓ Found Lufthansa-related results (filter likely applied)")
                    else:
                        print(
                            "        ⚠️  No Lufthansa results (filter may not have been extracted)"
                        )
        else:
            print(f"      ⚠️  Request failed: {response.status_code}")


def test_reranking(api_url: str, headers: dict, collection_id: str) -> None:
    """Test LLM reranking functionality."""
    print("\n  🎯 Testing LLM Reranking")

    query = "urgent payment issues"

    # Test with and without reranking
    for enable_reranking in [True, False]:
        print(f"\n    Reranking {'ENABLED' if enable_reranking else 'DISABLED'}")

        request_body = {
            "query": query,
            "enable_reranking": enable_reranking,
            "limit": 10,
            "response_type": "raw",
        }

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=request_body,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json()
            result_list = results.get("results", [])
            num_results = len(result_list)

            if num_results > 0:
                # Get scores to check if reranking changed the order
                scores = [r.get("score", 0) for r in result_list]
                avg_score = sum(scores) / len(scores) if scores else 0

                print(f"      ✓ {num_results} results returned")
                print(f"      Average score: {avg_score:.4f}")
                print(f"      Score range: {min(scores):.4f} - {max(scores):.4f}")

                # With reranking, top results should be more relevant
                if enable_reranking and num_results >= 3:
                    top_3_avg = sum(scores[:3]) / 3
                    print(f"      Top 3 average score: {top_3_avg:.4f}")
            else:
                print(f"      ⚠️  No results returned")
        else:
            print(f"      ⚠️  Request failed: {response.status_code}")


def test_recency_bias(api_url: str, headers: dict, collection_id: str) -> None:
    """Test recency bias configurations."""
    print("\n  📅 Testing Recency Bias")

    query = "invoice"
    bias_values = [0.0, 0.3, 0.7, 1.0]

    for bias in bias_values:
        print(f"\n    Testing recency_bias={bias}")

        request_body = {
            "query": query,
            "recency_bias": bias,
            "limit": 5,
            "response_type": "raw",
        }

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=request_body,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json()
            result_list = results.get("results", [])

            if result_list:
                # Check if results are ordered differently based on recency
                scores = [r.get("score", 0) for r in result_list]
                print(f"      ✓ {len(result_list)} results")
                print(f"      Scores: {[f'{s:.3f}' for s in scores[:3]]}...")

                # Try to extract dates from results to verify recency ordering
                # (This is approximate since we don't know exact data structure)
                for i, result in enumerate(result_list[:2]):
                    payload = result.get("payload", {})
                    # Look for date fields
                    for key in ["created_at", "updated_at", "date", "timestamp"]:
                        if key in payload:
                            print(
                                f"      Result {i+1} {key}: {payload[key][:10] if isinstance(payload[key], str) else payload[key]}"
                            )
                            break
            else:
                print(f"      ⚠️  No results returned")
        else:
            print(f"      ⚠️  Request failed: {response.status_code}")


def test_search_methods(api_url: str, headers: dict, collection_id: str) -> None:
    """Test different search methods (hybrid, neural, keyword)."""
    print("\n  🔍 Testing Search Methods")

    query = "Lufthansa invoice payment"
    methods = ["hybrid", "neural", "keyword"]

    for method in methods:
        print(f"\n    Testing {method} search")

        request_body = {
            "query": query,
            "search_method": method,
            "limit": 5,
            "response_type": "raw",
        }

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=request_body,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json()
            result_list = results.get("results", [])
            num_results = len(result_list)

            if num_results > 0:
                scores = [r.get("score", 0) for r in result_list]
                avg_score = sum(scores) / len(scores)
                print(f"      ✓ {method}: {num_results} results")
                print(f"      Average score: {avg_score:.4f}")

                # Check if keyword search finds exact matches
                if method == "keyword":
                    # Check if Lufthansa appears in top results
                    lufthansa_in_top = any(
                        "lufthansa" in json.dumps(r.get("payload", {})).lower()
                        for r in result_list[:2]
                    )
                    if lufthansa_in_top:
                        print("      ✓ Keyword search found exact match")
            else:
                print(f"      ⚠️  No results for {method} search")
        else:
            print(f"      ⚠️  {method} search failed: {response.status_code}")


def test_qdrant_filters(api_url: str, headers: dict, collection_id: str) -> None:
    """Test Qdrant native filtering."""
    print("\n  🎛️  Testing Qdrant Filters")

    # Test different filter configurations
    test_filters = [
        {
            "description": "Filter by source (if exists)",
            "filter": {"must": [{"key": "source_name", "match": {"value": "stripe"}}]},
        },
        {
            "description": "Complex filter with multiple conditions",
            "filter": {
                "should": [
                    {"key": "source_name", "match": {"value": "stripe"}},
                    {"key": "entity_type", "match": {"value": "invoice"}},
                ]
            },
        },
    ]

    for test_case in test_filters:
        print(f"\n    Test: {test_case['description']}")

        request_body = {
            "query": "payment",
            "filter": test_case["filter"],
            "limit": 5,
            "response_type": "raw",
        }

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=request_body,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json()
            num_results = len(results.get("results", []))
            print(f"      ✓ Filter applied: {num_results} results")

            # Check if filter was effective
            if num_results > 0:
                # Verify results match filter criteria
                first_result = results["results"][0]
                payload = first_result.get("payload", {})
                print(f"      First result source: {payload.get('source_name', 'unknown')}")
        else:
            print(f"      ⚠️  Filter test failed: {response.status_code}")
            if response.status_code == 422:
                print(f"      Invalid filter format: {response.text[:200]}")


def test_score_threshold(api_url: str, headers: dict, collection_id: str) -> None:
    """Test score threshold filtering."""
    print("\n  📊 Testing Score Threshold")

    query = "random unrelated query xyz123"
    thresholds = [None, 0.3, 0.5, 0.7]

    for threshold in thresholds:
        print(f"\n    Testing threshold={threshold}")

        request_body = {
            "query": query,
            "score_threshold": threshold,
            "limit": 10,
            "response_type": "raw",
        }

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=request_body,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json()
            result_list = results.get("results", [])
            num_results = len(result_list)

            if num_results > 0:
                scores = [r.get("score", 0) for r in result_list]
                min_score = min(scores) if scores else 0
                print(f"      ✓ {num_results} results (min score: {min_score:.4f})")

                # Verify all scores are above threshold
                if threshold is not None:
                    below_threshold = [s for s in scores if s < threshold]
                    if below_threshold:
                        print(f"      ⚠️  Found {len(below_threshold)} scores below threshold!")
                    else:
                        print(f"      ✓ All scores above threshold {threshold}")
            else:
                print(f"      No results (all filtered out or no matches)")
        else:
            print(f"      ⚠️  Request failed: {response.status_code}")


def test_pagination(api_url: str, headers: dict, collection_id: str) -> None:
    """Test pagination with offset and limit."""
    print("\n  📄 Testing Pagination")

    query = "invoice"

    # First, get total results
    response = requests.post(
        f"{api_url}/collections/{collection_id}/search",
        json={"query": query, "limit": 20, "response_type": "raw"},
        headers=headers,
    )

    if response.status_code != 200:
        print(f"    ⚠️  Initial search failed: {response.status_code}")
        return

    total_results = len(response.json().get("results", []))
    print(f"    Total available results: {total_results}")

    # Test pagination
    page_tests = [
        {"offset": 0, "limit": 5, "description": "First 5 results"},
        {"offset": 5, "limit": 5, "description": "Next 5 results"},
        {"offset": 10, "limit": 10, "description": "Results 11-20"},
    ]

    result_ids_seen = set()

    for test in page_tests:
        print(f"\n    {test['description']} (offset={test['offset']}, limit={test['limit']})")

        request_body = {
            "query": query,
            "offset": test["offset"],
            "limit": test["limit"],
            "response_type": "raw",
        }

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=request_body,
            headers=headers,
        )

        if response.status_code == 200:
            results = response.json()
            result_list = results.get("results", [])
            num_results = len(result_list)

            print(f"      ✓ Returned {num_results} results")

            # Check for duplicate results across pages
            for result in result_list:
                # Use payload content as ID since we might not have explicit IDs
                result_id = json.dumps(result.get("payload", {}))[:100]
                if result_id in result_ids_seen:
                    print(f"      ⚠️  Duplicate result found across pages!")
                result_ids_seen.add(result_id)

            # Verify we don't get more than requested
            if num_results > test["limit"]:
                print(f"      ⚠️  Got {num_results} results but limit was {test['limit']}")
        else:
            print(f"      ⚠️  Request failed: {response.status_code}")


def test_edge_cases(api_url: str, headers: dict, collection_id: str) -> None:
    """Test edge cases and error handling."""
    print("\n  ⚠️  Testing Edge Cases")

    edge_cases = [
        {
            "description": "Empty query",
            "body": {"query": "", "response_type": "raw"},
            "expected_status": 422,
        },
        {
            "description": "Very long query",
            "body": {"query": "a" * 1001, "response_type": "raw"},
            "expected_status": 422,
        },
        {
            "description": "Invalid response type",
            "body": {"query": "test", "response_type": "invalid"},
            "expected_status": 422,
        },
        {
            "description": "Negative offset",
            "body": {"query": "test", "offset": -1, "response_type": "raw"},
            "expected_status": 422,
        },
        {
            "description": "Limit exceeding maximum",
            "body": {"query": "test", "limit": 1001, "response_type": "raw"},
            "expected_status": 422,
        },
        {
            "description": "Invalid filter structure",
            "body": {
                "query": "test",
                "filter": {"invalid": "filter"},
                "response_type": "raw",
            },
            "expected_status": 422,
        },
        {
            "description": "Score threshold out of range",
            "body": {"query": "test", "score_threshold": 1.5, "response_type": "raw"},
            "expected_status": 422,
        },
        {
            "description": "Recency bias out of range",
            "body": {"query": "test", "recency_bias": 2.0, "response_type": "raw"},
            "expected_status": 422,
        },
    ]

    for test_case in edge_cases:
        print(f"\n    {test_case['description']}")

        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=test_case["body"],
            headers=headers,
        )

        if response.status_code == test_case["expected_status"]:
            print(f"      ✓ Got expected status {response.status_code}")
            if response.status_code == 422:
                # Check for validation error details
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        print(f"      Validation error: {str(error_detail)[:100]}...")
                except:
                    pass
        else:
            print(f"      ⚠️  Expected {test_case['expected_status']}, got {response.status_code}")
            print(f"      Response: {response.text[:200]}")

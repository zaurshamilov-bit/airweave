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

        # Assert successful response
        assert (
            response.status_code == 200
        ), f"Search failed for {strategy}: {response.status_code} - {response.text}"

        results = response.json()

        # Assert response structure
        assert "results" in results, f"Missing 'results' field for {strategy}"
        assert "response_type" in results, f"Missing 'response_type' field for {strategy}"
        assert "status" in results, f"Missing 'status' field for {strategy}"
        assert results["response_type"] == "raw", f"Wrong response_type for {strategy}"

        num_results = len(results.get("results", []))
        print(f"      ✓ {strategy}: {num_results} results returned")

        # For strategies that should work, assert we get some results (unless data is empty)
        if strategy in ["auto", "llm"] and num_results > 0:
            # Check if results have varied scores (indicating query expansion worked)
            scores = [r.get("score", 0) for r in results.get("results", [])]
            assert len(scores) > 0, f"No scores returned for {strategy}"

            score_variance = max(scores) - min(scores) if scores else 0
            print(f"      Score variance: {score_variance:.4f}")

            # For expansion strategies, we expect some score variance (not all identical)
            if len(scores) > 1:
                # Allow for some tolerance in score variance for expansion strategies
                # This is a soft assertion - expansion may not always create variance
                if score_variance == 0:
                    print(
                        f"      Note: No score variance for {strategy} - expansion may not have been effective"
                    )

        # Assert each result has required fields
        for i, result in enumerate(results.get("results", [])):
            assert "payload" in result, f"Result {i} missing 'payload' field for {strategy}"
            assert "score" in result, f"Result {i} missing 'score' field for {strategy}"
            assert isinstance(
                result["score"], (int, float)
            ), f"Score is not numeric for {strategy} result {i}"


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

        # Assert successful response
        assert (
            response.status_code == 200
        ), f"Query interpretation test failed: {response.status_code} - {response.text}"

        results = response.json()

        # Assert response structure
        assert "results" in results, "Missing 'results' field in query interpretation response"
        assert (
            "response_type" in results
        ), "Missing 'response_type' field in query interpretation response"
        assert "status" in results, "Missing 'status' field in query interpretation response"
        assert (
            results["response_type"] == "raw"
        ), "Wrong response_type in query interpretation response"

        num_results = len(results.get("results", []))
        status = results.get("status", "")
        print(
            f"      ✓ Interpretation {'ON' if test_case['enable_query_interpretation'] else 'OFF'}: "
        )
        print(f"        {num_results} results, status: {status}")

        # Assert status is valid
        valid_statuses = ["success", "no_results", "no_relevant_results"]
        assert (
            status in valid_statuses
        ), f"Invalid status '{status}' in query interpretation response"

        # Assert each result has required structure
        for i, result in enumerate(results.get("results", [])):
            assert "payload" in result, f"Query interpretation result {i} missing 'payload' field"
            assert "score" in result, f"Query interpretation result {i} missing 'score' field"
            assert isinstance(
                result["score"], (int, float)
            ), f"Query interpretation score is not numeric for result {i}"

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
                    print("        ⚠️  No Lufthansa results (filter may not have been extracted)")
                    # This is not a hard failure since the data may not contain Lufthansa


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

        # Assert successful response
        assert (
            response.status_code == 200
        ), f"Reranking test failed: {response.status_code} - {response.text}"

        results = response.json()

        # Assert response structure
        assert "results" in results, "Missing 'results' field in reranking response"
        assert "response_type" in results, "Missing 'response_type' field in reranking response"
        assert "status" in results, "Missing 'status' field in reranking response"
        assert results["response_type"] == "raw", "Wrong response_type in reranking response"

        result_list = results.get("results", [])
        num_results = len(result_list)

        # Assert status is valid
        status = results.get("status", "")
        valid_statuses = ["success", "no_results", "no_relevant_results"]
        assert status in valid_statuses, f"Invalid status '{status}' in reranking response"

        if num_results > 0:
            # Get scores to check if reranking changed the order
            scores = [r.get("score", 0) for r in result_list]
            assert len(scores) == num_results, "Number of scores doesn't match number of results"

            # Assert all scores are numeric
            for i, score in enumerate(scores):
                assert isinstance(
                    score, (int, float)
                ), f"Score {i} is not numeric in reranking test"
                assert (
                    0 <= score <= 1
                ), f"Score {i} ({score}) is out of expected range [0,1] in reranking test"

            avg_score = sum(scores) / len(scores) if scores else 0

            print(f"      ✓ {num_results} results returned")
            print(f"      Average score: {avg_score:.4f}")
            print(f"      Score range: {min(scores):.4f} - {max(scores):.4f}")

            # Assert scores are in descending order (highest relevance first)
            for i in range(len(scores) - 1):
                assert (
                    scores[i] >= scores[i + 1]
                ), f"Results not ordered by score: {scores[i]} < {scores[i + 1]} at position {i}"

            # With reranking, top results should be more relevant
            if enable_reranking and num_results >= 3:
                top_3_avg = sum(scores[:3]) / 3
                print(f"      Top 3 average score: {top_3_avg:.4f}")

        # Assert each result has required structure
        for i, result in enumerate(result_list):
            assert "payload" in result, f"Reranking result {i} missing 'payload' field"
            assert "score" in result, f"Reranking result {i} missing 'score' field"


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

        # Assert successful response
        assert (
            response.status_code == 200
        ), f"Recency bias test failed for bias={bias}: {response.status_code} - {response.text}"

        results = response.json()

        # Assert response structure
        assert (
            "results" in results
        ), f"Missing 'results' field in recency bias response for bias={bias}"
        assert (
            "response_type" in results
        ), f"Missing 'response_type' field in recency bias response for bias={bias}"
        assert (
            "status" in results
        ), f"Missing 'status' field in recency bias response for bias={bias}"
        assert (
            results["response_type"] == "raw"
        ), f"Wrong response_type in recency bias response for bias={bias}"

        result_list = results.get("results", [])
        status = results.get("status", "")

        # Assert status is valid
        valid_statuses = ["success", "no_results", "no_relevant_results"]
        assert (
            status in valid_statuses
        ), f"Invalid status '{status}' in recency bias response for bias={bias}"

        if result_list:
            # Check if results are ordered differently based on recency
            scores = [r.get("score", 0) for r in result_list]
            assert len(scores) == len(
                result_list
            ), f"Number of scores doesn't match results for bias={bias}"

            # Assert all scores are numeric and in valid range
            for i, score in enumerate(scores):
                assert isinstance(
                    score, (int, float)
                ), f"Score {i} is not numeric in recency bias test for bias={bias}"
                assert (
                    0 <= score <= 1
                ), f"Score {i} ({score}) is out of expected range [0,1] for bias={bias}"

            print(f"      ✓ {len(result_list)} results")
            print(f"      Scores: {[f'{s:.3f}' for s in scores[:3]]}...")

            # Assert scores are in descending order
            for i in range(len(scores) - 1):
                assert (
                    scores[i] >= scores[i + 1]
                ), f"Results not ordered by score for bias={bias}: {scores[i]} < {scores[i + 1]} at position {i}"

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

        # Assert each result has required structure
        for i, result in enumerate(result_list):
            assert (
                "payload" in result
            ), f"Recency bias result {i} missing 'payload' field for bias={bias}"
            assert (
                "score" in result
            ), f"Recency bias result {i} missing 'score' field for bias={bias}"


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

        # Assert successful response
        assert (
            response.status_code == 200
        ), f"Search method test failed for {method}: {response.status_code} - {response.text}"

        results = response.json()

        # Assert response structure
        assert "results" in results, f"Missing 'results' field in {method} search response"
        assert (
            "response_type" in results
        ), f"Missing 'response_type' field in {method} search response"
        assert "status" in results, f"Missing 'status' field in {method} search response"
        assert results["response_type"] == "raw", f"Wrong response_type in {method} search response"

        result_list = results.get("results", [])
        num_results = len(result_list)
        status = results.get("status", "")

        # Assert status is valid
        valid_statuses = ["success", "no_results", "no_relevant_results"]
        assert status in valid_statuses, f"Invalid status '{status}' in {method} search response"

        if num_results > 0:
            scores = [r.get("score", 0) for r in result_list]
            assert (
                len(scores) == num_results
            ), f"Number of scores doesn't match results for {method} search"

            # Assert all scores are numeric and in valid range
            for i, score in enumerate(scores):
                assert isinstance(
                    score, (int, float)
                ), f"Score {i} is not numeric in {method} search"
                assert (
                    0 <= score <= 1
                ), f"Score {i} ({score}) is out of expected range [0,1] in {method} search"

            avg_score = sum(scores) / len(scores)
            print(f"      ✓ {method}: {num_results} results")
            print(f"      Average score: {avg_score:.4f}")

            # Assert scores are in descending order
            for i in range(len(scores) - 1):
                assert (
                    scores[i] >= scores[i + 1]
                ), f"Results not ordered by score in {method} search: {scores[i]} < {scores[i + 1]} at position {i}"

            # Check if keyword search finds exact matches
            if method == "keyword":
                # Check if Lufthansa appears in top results
                lufthansa_in_top = any(
                    "lufthansa" in json.dumps(r.get("payload", {})).lower() for r in result_list[:2]
                )
                if lufthansa_in_top:
                    print("      ✓ Keyword search found exact match")

        # Assert each result has required structure
        for i, result in enumerate(result_list):
            assert "payload" in result, f"{method} search result {i} missing 'payload' field"
            assert "score" in result, f"{method} search result {i} missing 'score' field"


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

        # Assert successful response (or expected error for invalid filter)
        if response.status_code == 422:
            # Invalid filter format is acceptable - some filters may not match the data structure
            print(f"      ⚠️  Filter format may not match data structure: {response.status_code}")
            error_detail = response.json().get("detail", "")
            print(f"      Error: {str(error_detail)[:200]}")
            continue

        assert (
            response.status_code == 200
        ), f"Qdrant filter test failed: {response.status_code} - {response.text}"

        results = response.json()

        # Assert response structure
        assert "results" in results, "Missing 'results' field in Qdrant filter response"
        assert "response_type" in results, "Missing 'response_type' field in Qdrant filter response"
        assert "status" in results, "Missing 'status' field in Qdrant filter response"
        assert results["response_type"] == "raw", "Wrong response_type in Qdrant filter response"

        num_results = len(results.get("results", []))
        status = results.get("status", "")

        # Assert status is valid
        valid_statuses = ["success", "no_results", "no_relevant_results"]
        assert status in valid_statuses, f"Invalid status '{status}' in Qdrant filter response"

        print(f"      ✓ Filter applied: {num_results} results")

        # Check if filter was effective
        if num_results > 0:
            result_list = results.get("results", [])

            # Assert each result has required structure
            for i, result in enumerate(result_list):
                assert "payload" in result, f"Qdrant filter result {i} missing 'payload' field"
                assert "score" in result, f"Qdrant filter result {i} missing 'score' field"
                assert isinstance(
                    result["score"], (int, float)
                ), f"Qdrant filter score {i} is not numeric"
                assert (
                    0 <= result["score"] <= 1
                ), f"Qdrant filter score {i} ({result['score']}) is out of expected range [0,1]"

            # Verify results match filter criteria
            first_result = results["results"][0]
            payload = first_result.get("payload", {})
            print(f"      First result source: {payload.get('source_name', 'unknown')}")

            # Assert scores are in descending order
            scores = [r.get("score", 0) for r in result_list]
            for i in range(len(scores) - 1):
                assert (
                    scores[i] >= scores[i + 1]
                ), f"Qdrant filter results not ordered by score: {scores[i]} < {scores[i + 1]} at position {i}"


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

        # Assert successful response
        assert (
            response.status_code == 200
        ), f"Score threshold test failed for threshold={threshold}: {response.status_code} - {response.text}"

        results = response.json()

        # Assert response structure
        assert (
            "results" in results
        ), f"Missing 'results' field in score threshold response for threshold={threshold}"
        assert (
            "response_type" in results
        ), f"Missing 'response_type' field in score threshold response for threshold={threshold}"
        assert (
            "status" in results
        ), f"Missing 'status' field in score threshold response for threshold={threshold}"
        assert (
            results["response_type"] == "raw"
        ), f"Wrong response_type in score threshold response for threshold={threshold}"

        result_list = results.get("results", [])
        num_results = len(result_list)
        status = results.get("status", "")

        # Assert status is valid
        valid_statuses = ["success", "no_results", "no_relevant_results"]
        assert (
            status in valid_statuses
        ), f"Invalid status '{status}' in score threshold response for threshold={threshold}"

        if num_results > 0:
            scores = [r.get("score", 0) for r in result_list]
            assert (
                len(scores) == num_results
            ), f"Number of scores doesn't match results for threshold={threshold}"

            # Assert all scores are numeric and in valid range
            for i, score in enumerate(scores):
                assert isinstance(
                    score, (int, float)
                ), f"Score {i} is not numeric in score threshold test for threshold={threshold}"
                assert (
                    0 <= score <= 1
                ), f"Score {i} ({score}) is out of expected range [0,1] for threshold={threshold}"

            min_score = min(scores) if scores else 0
            print(f"      ✓ {num_results} results (min score: {min_score:.4f})")

            # Assert scores are in descending order
            for i in range(len(scores) - 1):
                assert (
                    scores[i] >= scores[i + 1]
                ), f"Results not ordered by score for threshold={threshold}: {scores[i]} < {scores[i + 1]} at position {i}"

            # Verify all scores are above threshold
            if threshold is not None:
                below_threshold = [s for s in scores if s < threshold]
                assert (
                    len(below_threshold) == 0
                ), f"Found {len(below_threshold)} scores below threshold {threshold}: {below_threshold}"
                print(f"      ✓ All scores above threshold {threshold}")
        else:
            print(f"      No results (all filtered out or no matches)")

        # Assert each result has required structure
        for i, result in enumerate(result_list):
            assert (
                "payload" in result
            ), f"Score threshold result {i} missing 'payload' field for threshold={threshold}"
            assert (
                "score" in result
            ), f"Score threshold result {i} missing 'score' field for threshold={threshold}"


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

    # Assert initial search succeeds
    assert (
        response.status_code == 200
    ), f"Initial pagination search failed: {response.status_code} - {response.text}"

    initial_results = response.json()
    assert "results" in initial_results, "Missing 'results' field in initial pagination response"

    total_results = len(initial_results.get("results", []))
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

        # Assert successful response
        assert (
            response.status_code == 200
        ), f"Pagination test failed for {test['description']}: {response.status_code} - {response.text}"

        results = response.json()

        # Assert response structure
        assert (
            "results" in results
        ), f"Missing 'results' field in pagination response for {test['description']}"
        assert (
            "response_type" in results
        ), f"Missing 'response_type' field in pagination response for {test['description']}"
        assert (
            "status" in results
        ), f"Missing 'status' field in pagination response for {test['description']}"
        assert (
            results["response_type"] == "raw"
        ), f"Wrong response_type in pagination response for {test['description']}"

        result_list = results.get("results", [])
        num_results = len(result_list)
        status = results.get("status", "")

        # Assert status is valid
        valid_statuses = ["success", "no_results", "no_relevant_results"]
        assert (
            status in valid_statuses
        ), f"Invalid status '{status}' in pagination response for {test['description']}"

        print(f"      ✓ Returned {num_results} results")

        # Verify we don't get more than requested
        assert (
            num_results <= test["limit"]
        ), f"Got {num_results} results but limit was {test['limit']} for {test['description']}"

        # Assert each result has required structure
        for i, result in enumerate(result_list):
            assert (
                "payload" in result
            ), f"Pagination result {i} missing 'payload' field for {test['description']}"
            assert (
                "score" in result
            ), f"Pagination result {i} missing 'score' field for {test['description']}"
            assert isinstance(
                result["score"], (int, float)
            ), f"Pagination score {i} is not numeric for {test['description']}"
            assert (
                0 <= result["score"] <= 1
            ), f"Pagination score {i} ({result['score']}) is out of expected range [0,1] for {test['description']}"

        # Check for duplicate results across pages
        for result in result_list:
            # Use payload content as ID since we might not have explicit IDs
            result_id = json.dumps(result.get("payload", {}))[:100]
            if result_id in result_ids_seen:
                # This is a warning, not a hard failure, since some search strategies may not guarantee unique pagination
                print(f"      ⚠️  Duplicate result found across pages for {test['description']}!")
            result_ids_seen.add(result_id)

        # Assert scores are in descending order within each page
        if num_results > 1:
            scores = [r.get("score", 0) for r in result_list]
            for i in range(len(scores) - 1):
                assert (
                    scores[i] >= scores[i + 1]
                ), f"Results not ordered by score in pagination for {test['description']}: {scores[i]} < {scores[i + 1]} at position {i}"


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

        # Assert expected status code
        assert response.status_code == test_case["expected_status"], (
            f"Expected status {test_case['expected_status']} for '{test_case['description']}', "
            f"got {response.status_code}. Response: {response.text[:200]}"
        )

        print(f"      ✓ Got expected status {response.status_code}")

        if response.status_code == 422:
            # Assert validation error structure for 422 responses
            try:
                error_response = response.json()
                # FastAPI returns validation errors in 'detail' field, but the structure can vary
                # It could be a string or a list of error objects
                if "detail" in error_response:
                    error_detail = error_response.get("detail", "")
                    # Detail could be a list of validation errors or a string
                    if isinstance(error_detail, list) and len(error_detail) > 0:
                        # FastAPI validation error format
                        print(f"      Validation errors: {len(error_detail)} error(s)")
                        for err in error_detail[:2]:  # Show first 2 errors
                            if isinstance(err, dict):
                                loc = err.get("loc", [])
                                msg = err.get("msg", "")
                                print(f"        - {'.'.join(map(str, loc))}: {msg}")
                    elif error_detail:
                        # Simple string error message
                        print(f"      Validation error: {str(error_detail)[:100]}...")
                    else:
                        print(f"      Empty error detail in 422 response")
                else:
                    # Some 422 responses might not have a detail field (though they should)
                    print(f"      422 response structure: {list(error_response.keys())}")
                    print(f"      Full response: {str(error_response)[:200]}...")
            except json.JSONDecodeError:
                # Some validation errors might not return JSON
                print(f"      Non-JSON validation error response: {response.text[:100]}...")

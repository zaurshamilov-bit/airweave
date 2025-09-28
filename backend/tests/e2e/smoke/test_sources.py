"""
Async test module for Sources endpoints.

Tests listing sources and getting source details.
These tests are completely independent and can run in parallel.
"""

import pytest
import httpx


class TestSources:
    """Test suite for Sources API endpoints."""

    @pytest.mark.asyncio
    async def test_list_sources(self, api_client: httpx.AsyncClient):
        """Test listing all available sources."""
        response = await api_client.get("/sources/list")

        assert response.status_code == 200, f"Failed to list sources: {response.text}"

        sources = response.json()
        assert isinstance(sources, list), "Sources response should be a list"
        assert len(sources) > 0, "Should have at least one source"

        # Check structure of first source
        first_source = sources[0]
        assert "short_name" in first_source
        assert "name" in first_source
        assert "description" in first_source
        assert "auth_methods" in first_source
        # icon_url is optional

    @pytest.mark.asyncio
    async def test_get_source_by_name(self, api_client: httpx.AsyncClient):
        """Test getting a specific source by short_name."""
        # Test with a known source (stripe should always exist)
        response = await api_client.get("/sources/detail/stripe")

        assert response.status_code == 200, f"Failed to get source: {response.text}"

        source = response.json()
        assert source["short_name"] == "stripe"
        assert "name" in source
        assert "description" in source
        assert "auth_methods" in source
        # icon_url, config_schema and credential_schema are optional
        # But check auth and config fields which should be present
        assert "auth_fields" in source
        assert "config_fields" in source

    @pytest.mark.asyncio
    async def test_get_multiple_sources(self, api_client: httpx.AsyncClient):
        """Test getting details for multiple known sources."""
        known_sources = ["stripe", "notion", "linear", "asana", "hubspot_crm"]

        for source_name in known_sources:
            response = await api_client.get(f"/sources/detail/{source_name}")

            # Some sources might not be available in all environments
            if response.status_code == 200:
                source = response.json()
                assert source["short_name"] == source_name
                assert "auth_methods" in source

    @pytest.mark.asyncio
    async def test_source_auth_methods(self, api_client: httpx.AsyncClient):
        """Test that sources have valid auth methods."""
        response = await api_client.get("/sources/list")
        sources = response.json()

        valid_auth_methods = [
            "direct",
            "oauth_browser",
            "oauth_token",
            "auth_provider",
            "oauth_byoc",
        ]

        for source in sources:
            assert "auth_methods" in source
            for auth_method in source["auth_methods"]:
                assert auth_method in valid_auth_methods, f"Invalid auth method: {auth_method}"

    @pytest.mark.asyncio
    async def test_source_not_found(self, api_client: httpx.AsyncClient):
        """Test error handling for non-existent source."""
        response = await api_client.get("/sources/detail/non_existent_source_xyz")

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()

    @pytest.mark.asyncio
    async def test_sources_have_required_fields(self, api_client: httpx.AsyncClient):
        """Test that all sources have required fields."""
        response = await api_client.get("/sources/list")
        sources = response.json()

        required_fields = ["short_name", "name", "description", "auth_methods"]

        for source in sources:
            for field in required_fields:
                assert (
                    field in source
                ), f"Source {source.get('short_name', 'unknown')} missing field: {field}"
                assert source[field] is not None, f"Source {source['short_name']} has null {field}"

    @pytest.mark.asyncio
    async def test_source_fields_structure(self, api_client: httpx.AsyncClient):
        """Test that source fields have proper structure."""
        # Get a source with fields
        response = await api_client.get("/sources/detail/stripe")
        source = response.json()

        # Check auth_fields structure
        if "auth_fields" in source and source["auth_fields"]:
            auth_fields = source["auth_fields"]
            assert "fields" in auth_fields
            assert isinstance(auth_fields["fields"], list)
            if auth_fields["fields"]:
                first_field = auth_fields["fields"][0]
                assert "name" in first_field
                assert "type" in first_field
                assert "required" in first_field

        # Check config_fields structure
        if "config_fields" in source and source["config_fields"]:
            config_fields = source["config_fields"]
            assert "fields" in config_fields
            assert isinstance(config_fields["fields"], list)

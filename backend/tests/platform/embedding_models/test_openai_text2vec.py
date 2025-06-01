"""Tests for OpenAIText2Vec embedding model."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec


class TestOpenAIText2Vec:
    """Tests for the OpenAIText2Vec embedding model."""

    @pytest.fixture
    def model_class(self):
        """Return the OpenAIText2Vec class."""
        return OpenAIText2Vec

    @pytest.fixture
    def model_kwargs(self):
        """Return kwargs for model initialization."""
        return {"api_key": "test-api-key", "embedding_model": "text-embedding-3-small"}

    @pytest.fixture
    def model(self, model_class, model_kwargs):
        """Create and return a model instance."""
        return model_class(**model_kwargs)

    @pytest.mark.asyncio
    async def test_embed_empty_text(self, model):
        """Test embedding an empty string returns zero vector."""
        result = await model.embed("")
        assert isinstance(result, list)
        assert len(result) == model.vector_dimensions
        assert all(v == 0.0 for v in result)

    @pytest.mark.asyncio
    async def test_embed_many_empty_list(self, model):
        """Test embedding an empty list returns empty list."""
        result = await model.embed_many([])
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_embed_many_all_empty_strings(self, model):
        """Test embedding a list of empty strings returns zeros."""
        result = await model.embed_many(["", ""])
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == model.vector_dimensions for vec in result)
        assert all(all(v == 0.0 for v in vec) for vec in result)

    @pytest.mark.asyncio
    async def test_create_classmethod(self, model_class, model_kwargs):
        """Test the create class method works."""
        model = model_class.create(**model_kwargs)
        assert isinstance(model, model_class)
        for key, value in model_kwargs.items():
            assert getattr(model, key) == value

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_success(self, mock_get_client, model):
        """Test successful embedding of a single text."""
        # Mock client and response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = await model.embed("Test text")

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 1536  # Default dimensions for OpenAI

        # Verify get_client was called
        mock_get_client.assert_called_once()

        # Verify the API call
        mock_client.post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={
                "input": "Test text",
                "model": "text-embedding-3-small",
                "encoding_format": "float",
            },
        )

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_with_model_override(self, mock_get_client, model):
        """Test embedding with model override."""
        # Mock client and response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        await model.embed("Test text", model="text-embedding-3-large")

        # Verify the API call uses the overridden model
        mock_client.post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={
                "input": "Test text",
                "model": "text-embedding-3-large",
                "encoding_format": "float",
            },
        )

    @pytest.mark.asyncio
    async def test_embed_with_dimensions_override(self, model):
        """Test that dimensions override raises an error."""
        with pytest.raises(ValueError, match="Dimensions override not supported"):
            await model.embed("Test text", dimensions=512)

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_many_success(self, mock_get_client, model):
        """Test successful embedding of multiple texts."""
        # Mock client and response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3] * 512}, {"embedding": [0.4, 0.5, 0.6] * 512}]
        }
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        texts = ["Text 1", "Text 2"]
        result = await model.embed_many(texts)

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == 1536 for vec in result)

        # Verify the API call
        mock_client.post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={"input": texts, "model": "text-embedding-3-small", "encoding_format": "float"},
        )

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_many_with_some_empty(self, mock_get_client, model):
        """Test embedding of a mix of empty and non-empty texts."""
        # Mock client and response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        texts = ["", "Text 2"]
        result = await model.embed_many(texts)

        # Verify the result
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == 1536 for vec in result)
        assert all(v == 0.0 for v in result[0])  # First vector should be all zeros

        # Verify the API call only sends the non-empty text
        mock_client.post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={
                "input": ["Text 2"],  # Only non-empty text
                "model": "text-embedding-3-small",
                "encoding_format": "float",
            },
        )

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_many_with_model_override(self, mock_get_client, model):
        """Test embedding with model override."""
        # Mock client and response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        await model.embed_many(["Test text"], model="text-embedding-3-large")

        # Verify the API call uses the overridden model
        mock_client.post.assert_called_once_with(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            json={
                "input": ["Test text"],
                "model": "text-embedding-3-large",
                "encoding_format": "float",
            },
        )

    @pytest.mark.asyncio
    async def test_embed_many_with_dimensions_override(self, model):
        """Test that dimensions override raises an error."""
        with pytest.raises(ValueError, match="Dimensions override not supported"):
            await model.embed_many(["Test text"], dimensions=512)

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_retry_on_connection_error(self, mock_get_client, model):
        """Test that connection errors are retried."""
        # Mock client that fails twice then succeeds
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        # First two calls fail, third succeeds
        mock_client.post.side_effect = [
            httpx.ConnectError("Connection failed"),
            httpx.ConnectError("Connection failed again"),
            MagicMock(
                raise_for_status=AsyncMock(),
                json=lambda: {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
            )
        ]

        result = await model.embed("Test text")

        # Should succeed after retries
        assert isinstance(result, list)
        assert len(result) == 1536

        # Should have been called 3 times (initial + 2 retries)
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_no_retry_on_auth_error(self, mock_get_client, model):
        """Test that authentication errors are not retried."""
        # Mock client that returns 401
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        auth_error = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401, text="Invalid API key")
        )
        mock_client.post.side_effect = auth_error

        with pytest.raises(httpx.HTTPStatusError):
            await model.embed("Test text")

        # Should only be called once (no retries for auth errors)
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_many_retry_on_timeout(self, mock_get_client, model):
        """Test that timeout errors are retried for batch embedding."""
        # Mock client that times out twice then succeeds
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        # First two calls timeout, third succeeds
        mock_client.post.side_effect = [
            httpx.ConnectTimeout("Request timed out"),
            httpx.ConnectTimeout("Request timed out again"),
            MagicMock(
                raise_for_status=AsyncMock(),
                json=lambda: {"data": [{"embedding": [0.1, 0.2, 0.3] * 512}]}
            )
        ]

        result = await model.embed_many(["Test text"])

        # Should succeed after retries
        assert isinstance(result, list)
        assert len(result) == 1
        assert len(result[0]) == 1536

        # Should have been called 3 times (initial + 2 retries)
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_get_client_creates_shared_instance(self, model):
        """Test that get_client creates and reuses a shared client instance."""
        client1 = await model.get_client()
        client2 = await model.get_client()

        # Should return the same instance
        assert client1 is client2
        assert isinstance(client1, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_close_client(self, model):
        """Test that close method properly closes the client."""
        # Get a client first
        await model.get_client()
        assert model._client is not None

        # Close it
        await model.close()
        assert model._client is None

    @pytest.mark.asyncio
    @patch("airweave.platform.embedding_models.openai_text2vec.OpenAIText2Vec.get_client")
    async def test_embed_all_retries_exhausted(self, mock_get_client, model):
        """Test behavior when all retry attempts are exhausted."""
        # Mock client that always fails
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        connection_error = httpx.ConnectError("Persistent connection failure")
        mock_client.post.side_effect = connection_error

        with pytest.raises(httpx.ConnectError):
            await model.embed("Test text")

        # Should have been called 4 times (initial + 3 retries)
        assert mock_client.post.call_count == 4

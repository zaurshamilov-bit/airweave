"""Auth config."""



from app.platform.configs._base import BaseConfig


class AuthConfig(BaseConfig):
    """Authentication config schema."""

    pass

class OpenAIAuthConfig(AuthConfig):
    """OpenAI authentication credentials schema."""

    api_key: str

class URLAndAPIKeyAuthConfig(AuthConfig):
    """URL and API key authentication credentials schema."""

    url: str
    api_key: str

class WeaviateAuthConfig(AuthConfig):
    """Weaviate authentication credentials schema."""

    cluster_url: str
    api_key: str

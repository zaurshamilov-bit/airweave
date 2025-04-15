"""Configuration settings for the Airweave backend.

Wraps environment variables and provides defaults.
"""

import os
from typing import Optional

from pydantic import PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Pydantic settings class.

    Attributes:
    ----------
        PROJECT_NAME (str): The name of the project.
        LOCAL_DEVELOPMENT (Optional[bool]): Whether the application is running locally.
        LOCAL_CURSOR_DEVELOPMENT (Optional[bool]): Whether cursor development features are enabled.
        FIRST_SUPERUSER (str): The email address of the first superuser.
        FIRST_SUPERUSER_PASSWORD (str): The password of the first superuser.
        ENCRYPTION_KEY (str): The encryption key.
        POSTGRES_HOST (str): The PostgreSQL server hostname.
        POSTGRES_DB (str): The PostgreSQL database name.
        POSTGRES_USER (str): The PostgreSQL username.
        POSTGRES_PASSWORD (str): The PostgreSQL password.
        SQLALCHEMY_ASYNC_DATABASE_URI (Optional[PostgresDsn]): The SQLAlchemy async database URI.
        LOCAL_NGROK_SERVER (Optional[str]): The local ngrok server URL.
        RUN_ALEMBIC_MIGRATIONS (Optional[bool]): Whether to run the alembic migrations.
        RUN_DB_SYNC (Optional[bool]): Whether to run the system sync to process sources,
            destinations, and entity types.
        NEO4J_HOST (str): The Neo4j host.
        NEO4J_PORT (int): The Neo4j port.
        NEO4J_USER (str): The Neo4j username.
        NEO4J_PASSWORD (str): The Neo4j password.
        QDRANT_URL (str): The Qdrant URL.
        QDRANT_API_KEY (str): The Qdrant API key.
        TEXT2VEC_INFERENCE_URL (str): The URL for text2vec-transformers inference service.
    """

    PROJECT_NAME: str = "Airweave"
    LOCAL_DEVELOPMENT: Optional[bool] = False
    LOCAL_CURSOR_DEVELOPMENT: Optional[bool] = False
    FRONTEND_LOCAL_DEVELOPMENT_PORT: Optional[int] = 8080
    DTAP_ENVIRONMENT: Optional[str] = "local"

    FIRST_SUPERUSER: str
    FIRST_SUPERUSER_PASSWORD: str

    ENCRYPTION_KEY: str

    POSTGRES_HOST: str
    POSTGRES_DB: str = "airweave"
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    SQLALCHEMY_ASYNC_DATABASE_URI: Optional[PostgresDsn] = None

    LOCAL_NGROK_SERVER: Optional[str] = None

    RUN_ALEMBIC_MIGRATIONS: Optional[bool] = False
    RUN_DB_SYNC: Optional[bool] = True

    NEO4J_HOST: str = "neo4j"
    NEO4J_PORT: int = 7687
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

    @property
    def TEXT2VEC_INFERENCE_URL(self) -> str:
        """Get the appropriate Text2Vec inference URL based on deployment context.

        For Docker internal communication, use http://text2vec-transformers:8080
        For local development reaching Docker containers, use http://localhost:8000
        Use environment variable if explicitly set, otherwise determine by LOCAL_DEVELOPMENT flag

        Returns:
            str: The URL for the Text2Vec inference service
        """
        # If explicitly set in env vars, use that
        env_url = os.getenv("TEXT2VEC_INFERENCE_URL")
        if env_url:
            return env_url

        # Otherwise, choose based on deployment context
        if self.LOCAL_DEVELOPMENT:
            # Local dev accessing Docker-hosted service (uses port mapping in docker-compose)
            return "http://localhost:8000"
        else:
            # Inside Docker network (service-to-service)
            return "http://text2vec-transformers:8080"

    OPENAI_API_KEY: Optional[str] = None

    @field_validator("SQLALCHEMY_ASYNC_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> PostgresDsn:
        """Build the SQLAlchemy database URI.

        Args:
        ----
            v (Optional[str]): The value of the SQLALCHEMY_DATABASE_URI setting.
            info (ValidationInfo): The validation context containing all field values.

        Returns:
        -------
            PostgresDsn: The assembled SQLAlchemy async database URI.

        """
        if isinstance(v, str):
            return v

        if info.data.get("LOCAL_DEVELOPMENT"):
            host = "localhost"
        else:
            host = info.data.get("POSTGRES_HOST")

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=host,
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        )

    @property
    def api_url(self) -> str:
        """The server URL.

        Returns:
            str: The server URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return self.LOCAL_NGROK_SERVER
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://api.airweave.ai"
        return f"https://api.{self.DTAP_ENVIRONMENT}-airweave.com"

    @property
    def app_url(self) -> str:
        """The app URL.

        Returns:
            str: The app URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return f"http://localhost:{self.FRONTEND_LOCAL_DEVELOPMENT_PORT}"
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://app.airweave.ai"
        return f"https://app.{self.DTAP_ENVIRONMENT}-airweave.com"

    @property
    def docs_url(self) -> str:
        """The docs URL.

        Returns:
            str: The docs URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return f"http://localhost:{self.FRONTEND_LOCAL_DEVELOPMENT_PORT}"
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://docs.airweave.ai"
        return f"https://docs.{self.DTAP_ENVIRONMENT}-airweave.com"


settings = Settings()

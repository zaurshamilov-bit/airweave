"""The API module that contains the endpoints for embedding models."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.core import credentials
from app.models.integration_credential import IntegrationType
from app.platform.configs._base import Fields
from app.platform.locator import resources

router = APIRouter()


@router.get("/{short_name}", response_model=schemas.EmbeddingModelWithConfigFields)
async def read_embedding_model(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.EmbeddingModel:
    """Get embedding model by id.

    Args:
    ----
        db (AsyncSession): The database session.
        short_name (str): The short name of the embedding model.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.EmbeddingModel: The embedding model object.

    """
    embedding_model = await crud.embedding_model.get_by_short_name(db, short_name)
    if not embedding_model:
        raise HTTPException(status_code=404, detail="Embedding model not found")
    if embedding_model.auth_config_class:
        auth_config_class = resources.get_auth_config(embedding_model.auth_config_class)
        embedding_model.config_fields = Fields.from_config_class(auth_config_class)
    return embedding_model


@router.get("/", response_model=list[schemas.EmbeddingModel])
async def read_embedding_models(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.EmbeddingModel]:
    """Get all embedding models.

    Args:
    ----
        db (AsyncSession): The database session.
        user (schemas.User): The current user.

    Returns:
    -------
        list[schemas.EmbeddingModel]: The list of embedding models.

    """
    return await crud.embedding_model.get_multi(db)


@router.post("/connect/{short_name}", response_model=schemas.IntegrationCredential)
async def connect_to_embedding_model(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    config_fields: dict,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.EmbeddingModel:
    """Connect to an embedding model.

    Args:
    ----
        db (AsyncSession): The database session.
        short_name (str): The short name of the embedding model.
        config_fields (dict): The configuration fields.
        embedding_model_in (schemas.EmbeddingModelCreate): The embedding model to create.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.EmbeddingModel: The embedding model object.
    """
    embedding_model = await crud.embedding_model.get_by_short_name(db, short_name)
    if not embedding_model:
        raise HTTPException(status_code=400, detail="Embedding model does not exist")

    auth_config_class = resources.get_auth_config(embedding_model.auth_config_class)
    auth_config = auth_config_class(**config_fields)

    encrypted_credentials = credentials.encrypt(auth_config.model_dump())

    integration_credentials = schemas.IntegrationCredentialCreateEncrypted(
        name=f"{embedding_model.name} - {user.email}",
        description=f"Credentials for {embedding_model.name} - {user.email}",
        integration_short_name=embedding_model.short_name,
        integration_type=IntegrationType.EMBEDDING_MODEL,
        auth_credential_type=embedding_model.auth_config_class,
        encrypted_credentials=encrypted_credentials,
        auth_config_class=embedding_model.auth_config_class,
    )

    integration_credentials = await crud.integration_credential.create(
        db, obj_in=integration_credentials, current_user=user
    )

    integration_credentials.decrypted_credentials = credentials.decrypt(
        integration_credentials.encrypted_credentials
    )

    return integration_credentials

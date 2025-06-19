"""The API module that contains the endpoints for sources."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.platform.configs._base import Fields
from airweave.platform.locator import resource_locator
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


def _get_enriched_source(source: schemas.Source) -> schemas.Source:
    """Enrich the source object with auth and config fields.

    Returns the enriched source on success or an error string on failure.
    """
    if not source.auth_config_class:
        raise HTTPException(
            status_code=400,
            detail=f"Source {source.short_name} does not have authentication configuration",
        )

    if not source.config_class:
        raise HTTPException(
            status_code=400,
            detail=f"Source {source.short_name} does not have a configuration class",
        )

    try:
        auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
        auth_fields = Fields.from_config_class(auth_config_class)
        config_class = resource_locator.get_config(source.config_class)
        config_fields = Fields.from_config_class(config_class)
    except Exception as e:
        logger.error(f"Failed to get source config fields for {source.short_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid configuration for source {source.short_name}",
        ) from e

    source_dict = {
        **{key: getattr(source, key) for key in source.__dict__ if not key.startswith("_")},
        "auth_fields": auth_fields,
        "config_fields": config_fields,
    }
    return schemas.Source.model_validate(source_dict)


@router.get("/detail/{short_name}", response_model=schemas.Source)
async def read_source(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.Source:
    """Get source by id.

    Args:
    ----
        db (AsyncSession): The database session.
        short_name (str): The short name of the source.
        auth_context (AuthContext): The current authentication context.

    Returns:
    -------
        schemas.Source: The source object.

    Raises:
        HTTPException:
            - 404 if source not found
            - 400 if source missing required configuration classes
            - 500 if there's an error retrieving auth configuration
    """
    try:
        source = await crud.source.get_by_short_name(db, short_name)
        enriched_source = _get_enriched_source(source)

        if isinstance(enriched_source, str):
            status_code = 400 if "does not have" in enriched_source else 500
            raise HTTPException(status_code=status_code, detail=enriched_source)

        return enriched_source

    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=f"Source {short_name} not found") from e
    except Exception as e:
        logger.exception(f"Error retrieving source {short_name}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve source details for {short_name}"
        ) from e


@router.get("/list", response_model=list[schemas.Source])
async def read_sources(
    *,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> list[schemas.Source]:
    """Get all sources with their authentication fields."""
    sources = await crud.source.get_all(db)
    return sources

"""White label endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.core import credentials
from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.db.unit_of_work import UnitOfWork
from app.models.integration_credential import IntegrationType
from app.models.user import User
from app.models.white_label import WhiteLabel
from app.platform.auth.schemas import AuthType
from app.platform.auth.services import oauth2_service
from app.schemas.connection import ConnectionCreate, ConnectionStatus
from app.schemas.white_label import WhiteLabelCreate, WhiteLabelUpdate

router = APIRouter()


@router.get("/list", response_model=List[WhiteLabel])
async def list_white_label_integrations(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> List[WhiteLabel]:
    """List all white label integrations for the current user's organization."""
    integrations = await crud.white_label.get_all_for_organization(
        db, org_id=current_user.organization_id
    )
    return integrations


@router.post("/", response_model=WhiteLabel)
async def create_white_label_integration(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
    integration_in: WhiteLabelCreate,
) -> WhiteLabel:
    """Create new white label integration."""
    integration = await crud.white_label.create(
        db,
        obj_in=integration_in,
        created_by_email=current_user.email,
        organization_id=current_user.organization_id,
    )
    return integration


@router.get("/{white_label_id}", response_model=WhiteLabel)
async def get_white_label_integration(
    white_label_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> WhiteLabel:
    """Get a specific white label integration."""
    white_label = await crud.white_label.get(db, id=white_label_id)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return white_label


@router.put("/{white_label_id}", response_model=WhiteLabel)
async def update_white_label_integration(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
    white_label_id: UUID,
    white_label_in: WhiteLabelUpdate,
) -> WhiteLabel:
    """Update a white label integration."""
    # TODO: Check if update is valid (i.e. scopes, source id etc)
    white_label = await crud.white_label.get(db, id=white_label_id)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    white_label = await crud.white_label.update(
        db,
        db_obj=white_label,
        obj_in=white_label_in,
        modified_by_email=current_user.email,
    )
    return white_label


@router.delete("/{white_label_id}")
async def delete_white_label_integration(
    white_label_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> dict:
    """Delete a white label integration."""
    white_label = await crud.white_label.get(db, id=white_label_id)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return await crud.white_label.remove(db, id=white_label_id)


@router.get("/{white_label_id}/oauth2/auth_url", response_model=str)
async def get_whitelabel_oauth2_auth_url(
    *,
    db: AsyncSession = Depends(deps.get_db),
    white_label_id: UUID,
    user: User = Depends(deps.get_user),
) -> str:
    """Generate the OAuth2 authorization URL by delegating to oauth2_service."""
    white_label = await crud.white_label.get(db, id=white_label_id)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return oauth2_service.generate_auth_url_for_whitelabel(white_label)


@router.post("/{white_label_id}/oauth2/code", response_model=schemas.Connection)
async def exchange_whitelabel_oauth2_code(
    *,
    white_label_id: UUID,
    code: str = Body(...),
    db: AsyncSession = Depends(deps.get_db),
    user: User = Depends(deps.get_user),
) -> schemas.Connection:
    """Exchange OAuth2 code for tokens and create connection."""
    white_label = await crud.white_label.get(db, id=white_label_id)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    try:
        token_response = await oauth2_service.exchange_code_for_whitelabel(
            db, code, white_label, user
        )
    except Exception as e:
        logger.error(f"Failed to exchange OAuth2 code for WhiteLabel {white_label.id}: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth2 code.") from e

    decrypted_credentials = {
        "access_token": token_response.access_token,
        "refresh_token": token_response.refresh_token,
    }
    encrypted_credentials = credentials.encrypt(decrypted_credentials)

    async with UnitOfWork(db) as uow:
        source = await crud.source.get_by_short_name(uow.session, short_name=white_label.source_id)
        if not source:
            raise NotFoundException(
                f"No Source found matching white_label.source_id='{white_label.source_id}'"
            )

        integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"WhiteLabel {white_label.name} - {user.email}",
            description=f"Credentials for WhiteLabel {white_label.name}",
            integration_short_name=source.short_name,
            integration_type=IntegrationType.SOURCE,
            auth_type=AuthType.oauth2,
            encrypted_credentials=encrypted_credentials,
            auth_config_class=None,
        )
        integration_cred = await crud.integration_credential.create(
            uow.session, obj_in=integration_cred_in, current_user=user, uow=uow
        )
        await uow.session.flush()

        connection_in = ConnectionCreate(
            name=f"WhiteLabel Connection - {white_label.name}",
            integration_type=IntegrationType.SOURCE,
            status=ConnectionStatus.ACTIVE,
            integration_credential_id=integration_cred.id,
            source_id=source.id,
        )
        connection = await crud.connection.create(
            uow.session, obj_in=connection_in, current_user=user, uow=uow
        )

        await uow.commit()
        await uow.session.refresh(connection)

    return connection

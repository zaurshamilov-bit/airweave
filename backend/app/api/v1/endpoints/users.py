"""The API module that contains the endpoints for users.

Important: this module is co-responsible with the CRUD layer for secure transactions with the
database, as it contains the endpoints for user creation and retrieval.
"""

from fastapi import APIRouter, Depends

from app import schemas
from app.api import deps
from app.schemas import User

router = APIRouter()


@router.get("/", response_model=User)
async def read_user(
    *,
    current_user: User = Depends(deps.get_user),
) -> schemas.User:
    """Get current user.

    Args:
    ----
        current_user (User): The current user.

    Returns:
    -------
        schemas.User: The user object.

    """
    return current_user

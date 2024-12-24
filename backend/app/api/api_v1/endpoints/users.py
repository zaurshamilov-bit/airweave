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

# @router.post("/create_if_not_exists", response_model=schemas.User)
# async def create_if_not_exists(
#     *,
#     db: AsyncSession = Depends(deps.get_db),
#     user_in: schemas.UserCreate,
# ) -> schemas.User:
#     """Create new user in database if it does not exist.

#     Can only create user with the same email as the authenticated user.

#     Args:
#         db (AsyncSession): Database session dependency to handle database operations.
#         user_in (schemas.UserCreate): The user object to be created.
#         current_auth0_user (Auth0User): Authenticated auth0 user.

#     Returns:
#         schemas.User: The created user object.

#     Raises:
#         HTTPException: If the user is not authorized to create this user.
#     """
#     if user_in.email != current_auth0_user.email:
#         raise HTTPException(
#             status_code=403,
#             detail="You are not authorized to create this user.",
#         )

#     user = await crud.user.get_by_email(db, email=user_in.email)

#     if user:
#         return user

#     user = await crud.user.create(db, obj_in=user_in)
#     return user

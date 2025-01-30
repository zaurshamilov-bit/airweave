"""CRUD operations for chats."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core.exceptions import NotFoundException
from app.crud._base import CRUDBase
from app.db.unit_of_work import UnitOfWork
from app.models.chat import Chat, ChatMessage


class CRUDChat(CRUDBase[Chat, schemas.ChatCreate, schemas.ChatUpdate]):
    """CRUD operations for chats."""

    async def get_with_messages(
        self, db: AsyncSession, id: UUID, current_user: schemas.User
    ) -> Optional[schemas.Chat]:
        """Get a chat by ID including its messages.

        Args:
            db (AsyncSession): The database session
            id (UUID): The chat ID
            current_user (schemas.User): The current user

        Returns:
            Optional[Chat]: The chat with messages
        """
        stmt = select(Chat).where(Chat.id == id)
        result = await db.execute(stmt)
        chat = result.unique().scalar_one_or_none()

        if chat:
            self._validate_if_user_has_permission(chat, current_user)

        return chat

    async def get_active_chats(
        self, db: AsyncSession, current_user: schemas.User, *, skip: int = 0, limit: int = 100
    ) -> list[schemas.Chat]:
        """Get all active chats for a user.

        Args:
            db (AsyncSession): The database session
            current_user (schemas.User): The current user
            skip (int): Number of records to skip
            limit (int): Maximum number of records to return

        Returns:
            list[schemas.Chat]: List of active chats
        """
        query = (
            select(Chat)
            .where(
                (Chat.created_by_email == current_user.email)
                | (Chat.modified_by_email == current_user.email)
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def add_message(
        self,
        db: AsyncSession,
        *,
        chat_id: UUID,
        obj_in: schemas.ChatMessageCreate,
        current_user: schemas.User,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.ChatMessage:
        """Add a message to a chat.

        Args:
            db (AsyncSession): The database session
            chat_id (UUID): The chat ID
            obj_in (schemas.ChatMessageCreate): The message to create
            current_user (schemas.User): The current user
            uow (Optional[UnitOfWork]): Optional unit of work for transaction management

        Returns:
            schemas.ChatMessage: The created message

        Raises:
            NotFoundException: If the chat is not found
        """
        # First verify chat exists and user has permission
        chat = await self.get(db, id=chat_id, current_user=current_user)
        if not chat:
            raise NotFoundException("Chat not found")

        # Convert to dict if it's not already
        if not isinstance(obj_in, dict):
            obj_in_data = obj_in.model_dump()
        else:
            obj_in_data = obj_in

        # Create the message object with all required fields
        db_obj = ChatMessage(
            **obj_in_data,
            chat_id=chat_id,
            organization_id=current_user.organization_id,
            created_by_email=current_user.email,
            modified_by_email=current_user.email,
        )

        db.add(db_obj)
        if not uow:
            await db.commit()
            await db.refresh(db_obj)

        return db_obj


chat = CRUDChat(Chat)

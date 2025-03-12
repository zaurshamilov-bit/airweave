"""Chat models for the platform."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy import Enum as SQLAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.shared_models import ChatRole
from airweave.models._base import OrganizationBase, UserMixin


class Chat(OrganizationBase, UserMixin):
    """Chat model representing a conversation.

    Attributes:
        name: Name of the chat
        description: Optional description
        status: Current status of the chat (active/archived)
        model_name: Name of the AI model being used
        model_settings: JSON field for model-specific settings
        messages: Relationship to chat messages
    """

    __tablename__ = "chat"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sync_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("sync.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_settings: Mapped[dict] = mapped_column(JSON, default={}, nullable=False)
    search_settings: Mapped[dict] = mapped_column(JSON, default={}, nullable=False)

    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="chat", lazy="selectin", cascade="all, delete-orphan"
    )


class ChatMessage(OrganizationBase, UserMixin):
    """Message within a chat.

    Attributes:
        chat_id: Foreign key to parent chat
        content: Message content
        role: Role of the message sender
        tokens_used: Number of tokens used for this message
        metadata: Additional message metadata
        chat: Relationship to parent chat
    """

    __tablename__ = "chat_message"

    chat_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[ChatRole] = mapped_column(SQLAEnum(ChatRole), nullable=False)
    tokens_used: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages", lazy="joined")

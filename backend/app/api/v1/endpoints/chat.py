"""Chat endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api.deps import get_db, get_user
from app.core.chat_service import chat_service
from app.core.logging import logger

router = APIRouter()


@router.post("/", response_model=schemas.Chat)
async def create_chat(
    *,
    db: AsyncSession = Depends(get_db),
    chat_in: schemas.ChatCreate,
    user: schemas.User = Depends(get_user),
) -> schemas.Chat:
    """Create a new chat."""
    chat = await crud.chat.create(db=db, obj_in=chat_in, current_user=user)
    return chat


@router.get("/", response_model=list[schemas.Chat])
async def list_chats(
    *,
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: schemas.User = Depends(get_user),
) -> list[schemas.Chat]:
    """List all chats for the current user."""
    chats = await crud.chat.get_active_chats(db=db, current_user=user, skip=skip, limit=limit)
    return chats


@router.get("/{chat_id}", response_model=schemas.Chat)
async def get_chat(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    user: schemas.User = Depends(get_user),
) -> schemas.Chat:
    """Get a specific chat by ID."""
    chat = await crud.chat.get_with_messages(db=db, id=chat_id, current_user=user)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


@router.put("/{chat_id}", response_model=schemas.Chat)
async def update_chat(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    chat_in: schemas.ChatUpdate,
    user: schemas.User = Depends(get_user),
) -> schemas.Chat:
    """Update a chat."""
    chat = await crud.chat.get(db=db, id=chat_id, current_user=user)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    chat = await crud.chat.update(db=db, db_obj=chat, obj_in=chat_in, current_user=user)
    return chat


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    user: schemas.User = Depends(get_user),
) -> None:
    """Archive a chat."""
    chat = await crud.chat.get(db=db, id=chat_id, current_user=user)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    await crud.chat.remove(db=db, id=chat_id, current_user=user)


@router.post("/{chat_id}/message")
async def send_message(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    message: schemas.ChatMessageCreate,
    user: schemas.User = Depends(get_user),
) -> schemas.ChatMessage:
    """Send a message to a chat."""
    return await crud.chat.add_message(db=db, chat_id=chat_id, obj_in=message, current_user=user)


@router.get("/{chat_id}/stream", response_class=StreamingResponse)
async def stream_chat_response(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    user: schemas.User = Depends(get_user),
) -> StreamingResponse:
    """Stream an AI response for a chat message."""

    async def event_generator():
        buffer = ""
        try:
            async for chunk in chat_service.generate_streaming_response(
                db=db, chat_id=chat_id, user=user
            ):
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content

                    # Add to buffer and check for complete words/markdown
                    buffer += content

                    # Only send if we have a complete word or markdown element
                    if buffer.endswith((" ", "\n", "|", ".", ",", ":", "-")):
                        yield f"data: {buffer}\n\n"
                        buffer = ""

            # Send any remaining content in buffer
            if buffer:
                yield f"data: {buffer}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error in stream: {str(e)}")
            yield "data: [ERROR]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
        },
    )

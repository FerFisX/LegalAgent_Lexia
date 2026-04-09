"""
Endpoints del chat:
- POST /chat              → envía mensaje y obtiene respuesta del agente
- GET  /chat/conversations → lista conversaciones del usuario
- GET  /chat/{id}         → obtiene conversación completa con mensajes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.user import User
from backend.models.conversation import Conversation
from backend.schemas.chat import ChatRequest, ChatResponse, ConversationResponse
from backend.services.chat_service import process_message
from backend.api.middleware.auth_middleware import get_current_user_or_guest


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
):
    """
    Envía un mensaje al agente Lexia y recibe orientación legal.
    Disponible para usuarios registrados e invitados (con límite).
    """
    if not body.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mensaje no puede estar vacío",
        )

    result = await process_message(
        user_message=body.message,
        user=current_user,
        conversation_id=body.conversation_id,
        db=db,
    )

    return ChatResponse(**result)


@router.get("/conversations", response_model=list[ConversationResponse])
def get_conversations(
    current_user: User = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
):
    """Lista todas las conversaciones del usuario."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return conversations


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
):
    """Obtiene una conversación completa con todos sus mensajes."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada",
        )

    return conversation

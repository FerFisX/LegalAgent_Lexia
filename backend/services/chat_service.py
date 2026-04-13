"""
Servicio de chat: orquesta el agente LangGraph y persiste en PostgreSQL.
"""

import uuid
from langchain_core.messages import HumanMessage
from loguru import logger
from sqlalchemy.orm import Session

from backend.agent.graph import agent_graph
from backend.agent.state import AgentState
from backend.models.conversation import Conversation, Message
from backend.models.user import User
from backend.core.config import settings


def _build_initial_state(
    user_message: str,
    history: list[Message],
) -> AgentState:
    """Construye el estado inicial del agente desde el historial de la DB."""
    lc_messages = []

    for msg in history:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        else:
            from langchain_core.messages import AIMessage
            lc_messages.append(AIMessage(content=msg.content))

    lc_messages.append(HumanMessage(content=user_message))

    return AgentState(
        messages=lc_messages,
        user_problem=user_message,
    )


async def process_message(
    user_message: str,
    user: User,
    conversation_id: str | None,
    db: Session,
) -> dict:
    """
    Procesa un mensaje del usuario:
    1. Obtiene o crea la conversación
    2. Guarda el mensaje del usuario
    3. Ejecuta el agente LangGraph
    4. Guarda la respuesta del agente
    5. Retorna la respuesta con metadata

    Returns:
        Dict con conversation_id, respuesta, áreas, complejidad, abogados, procesos
    """

    # ── 1. Obtener o crear conversación ───────────────────────────
    if conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        ).first()
        if not conversation:
            conversation = None  # no encontrada, crear nueva

    if not conversation_id or not conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title=user_message[:60] + "..." if len(user_message) > 60 else user_message,
        )
        db.add(conversation)
        db.flush()

    # ── 2. Guardar mensaje del usuario ────────────────────────────
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    db.flush()

    # ── 3. Construir historial y ejecutar agente ──────────────────
    history = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.id != user_msg.id,
    ).order_by(Message.created_at).all()

    state = _build_initial_state(user_message, history)

    logger.info(f"Ejecutando agente para conversación: {conversation.id}")
    result = agent_graph.invoke(state)

    # ── 4. Extraer resultado del estado final ─────────────────────
    final_response = result.get("final_response", "")
    if not final_response and result.get("messages"):
        final_response = result["messages"][-1].content

    detected_areas = result.get("detected_areas", [])
    complexity = result.get("complexity", "")
    suggested_lawyers = result.get("suggested_lawyers", [])
    suggested_processes = result.get("suggested_processes", [])
    needs_lawyer = result.get("needs_lawyer", False)

    # ── 5. Guardar respuesta del agente ───────────────────────────
    agent_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        role="assistant",
        content=final_response,
        agent_metadata={
            "detected_areas": detected_areas,
            "complexity": complexity,
            "needs_lawyer": needs_lawyer,
            "lawyers_count": len(suggested_lawyers),
        },
    )
    db.add(agent_msg)

    # Actualizar conversación
    conversation.detected_areas = detected_areas
    conversation.complexity = complexity
    conversation.status = "referred_to_lawyer" if needs_lawyer else "active"

    # Incrementar contador de invitado si aplica
    if user.is_guest:
        user.guest_query_count += 1

    db.commit()
    db.refresh(agent_msg)

    return {
        "conversation_id": conversation.id,
        "message": agent_msg,
        "detected_areas": detected_areas,
        "complexity": complexity,
        "suggested_lawyers": suggested_lawyers if needs_lawyer else [],
        "suggested_processes": suggested_processes,
    }

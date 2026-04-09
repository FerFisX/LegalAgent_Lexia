"""
Estado del agente LangGraph.
Contiene toda la información que fluye entre los nodos del grafo.
"""

from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    Estado completo del agente durante una conversación.
    LangGraph actualiza este estado en cada nodo.
    """

    # Historial de mensajes (user + assistant)
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # Problema del usuario en texto plano
    user_problem: str = ""

    # Áreas legales detectadas (penal, civil, laboral, etc.)
    detected_areas: list[str] = Field(default_factory=list)

    # Contexto legal recuperado del RAG
    legal_context: str = ""

    # Procesos legales aplicables
    suggested_processes: list[dict] = Field(default_factory=list)

    # Abogados recomendados
    suggested_lawyers: list[dict] = Field(default_factory=list)

    # Complejidad evaluada: "simple" | "moderate" | "complex"
    complexity: str = ""

    # Preguntas pendientes para clarificar el caso
    pending_questions: list[str] = Field(default_factory=list)

    # ¿El caso necesita derivación a abogado?
    needs_lawyer: bool = False

    # Ciudad del usuario para filtrar abogados
    user_city: str | None = None

    # Respuesta final generada
    final_response: str = ""

    # Iteraciones de clarificación realizadas
    clarification_rounds: int = 0

    # Máximo de rondas de clarificación antes de proceder
    max_clarification_rounds: int = 2

"""
Nodo 5: Generar la respuesta final al ciudadano.
Dos caminos: orientación directa O derivación a abogado.
"""

from langchain_core.messages import AIMessage, HumanMessage
from loguru import logger

from backend.agent.state import AgentState
from backend.agent.llm import get_llm
from backend.agent.prompts import RAG_PROMPT, LAWYER_RECOMMENDATION_PROMPT, SYSTEM_PROMPT


def respond_node(state: AgentState) -> dict:
    """Genera respuesta de orientación legal basada en el RAG."""
    logger.info("Nodo: respond (orientación directa)")

    processes_text = ""
    if state.suggested_processes:
        processes_text = "\n".join([
            f"- {p['nombre']} ({p['institucion']}): {p['pasos']}"
            for p in state.suggested_processes[:2]
        ])

    prompt = RAG_PROMPT.format(
        problem=state.user_problem,
        legal_context=state.legal_context or "No se encontró legislación específica.",
        processes=processes_text or "No se encontraron procesos específicos.",
    )

    llm = get_llm()
    response = llm.invoke([
        HumanMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    return {
        "messages": [AIMessage(content=response.content)],
        "final_response": response.content,
    }


def refer_lawyer_node(state: AgentState) -> dict:
    """Genera respuesta derivando al ciudadano a un abogado especialista."""
    logger.info("Nodo: refer_lawyer (caso complejo)")

    lawyers_text = ""
    if state.suggested_lawyers:
        lawyers_text = "\n".join([
            f"- {l['nombre']} | {l['ciudad']} | Tel: {l['telefono']} | "
            f"Esp: {', '.join(l.get('especialidades', []))}"
            for l in state.suggested_lawyers[:3]
        ])
    else:
        lawyers_text = "No hay abogados registrados en tu ciudad aún. "
        lawyers_text += "Puedes consultar el Colegio de Abogados de Bolivia."

    prompt = LAWYER_RECOMMENDATION_PROMPT.format(
        problem=state.user_problem,
        areas=", ".join(state.detected_areas),
        lawyers=lawyers_text,
    )

    llm = get_llm()
    response = llm.invoke([
        HumanMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    return {
        "messages": [AIMessage(content=response.content)],
        "final_response": response.content,
        "needs_lawyer": True,
    }

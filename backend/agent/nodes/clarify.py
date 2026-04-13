"""
Nodo 2: Hacer preguntas de clarificación si falta contexto.
"""

from langchain_core.messages import AIMessage
from loguru import logger

from backend.agent.state import AgentState
from backend.agent.llm import get_llm
from backend.agent.prompts import CLARIFICATION_PROMPT


def clarify_node(state: AgentState) -> dict:
    """
    Genera una pregunta de clarificación para obtener más contexto.
    Máximo max_clarification_rounds rondas.
    """
    logger.info(f"Nodo: clarify (ronda {state.clarification_rounds + 1})")

    history = "\n".join([
        f"{'Usuario' if hasattr(m, 'type') and m.type == 'human' else 'Lexia'}: {m.content}"
        for m in state.messages[-6:]  # últimos 6 mensajes
    ])

    prompt = CLARIFICATION_PROMPT.format(
        problem=state.user_problem,
        history=history,
        questions="\n".join(state.pending_questions),
    )

    llm = get_llm()
    response = llm.invoke([{"role": "user", "content": prompt}])
    question = response.content

    return {
        "messages": [AIMessage(content=question)],
        "clarification_rounds": state.clarification_rounds + 1,
        "final_response": question,
    }

"""
Nodo 4: Evaluar complejidad del caso y decidir si derivar a abogado.
"""

import json
from langchain_core.messages import HumanMessage
from loguru import logger

from backend.agent.state import AgentState
from backend.agent.llm import get_llm
from backend.agent.prompts import COMPLEXITY_PROMPT


def evaluate_node(state: AgentState) -> dict:
    """
    Evalúa la complejidad real del caso una vez que se tiene
    el contexto legal recuperado. Decide si derivar a abogado.
    """
    logger.info("Nodo: evaluate")

    context_summary = state.legal_context[:500] if state.legal_context else "Sin contexto"

    prompt = COMPLEXITY_PROMPT.format(
        problem=state.user_problem,
        areas=", ".join(state.detected_areas),
        context_summary=context_summary,
    )

    llm = get_llm()

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())

        return {
            "complexity": result.get("complexity", "moderate"),
            "needs_lawyer": result.get("needs_lawyer", False),
        }

    except Exception as e:
        logger.error(f"Error en evaluate_node: {e}")
        return {
            "complexity": "moderate",
            "needs_lawyer": False,
        }

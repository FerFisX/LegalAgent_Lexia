"""
Nodo 1: Clasificar intención y detectar áreas legales.
"""

import json
from langchain_core.messages import HumanMessage
from loguru import logger

from backend.agent.state import AgentState
from backend.agent.llm import get_llm
from backend.agent.prompts import CLASSIFY_PROMPT


def classify_node(state: AgentState) -> dict:
    """
    Analiza el problema del usuario y detecta:
    - Áreas legales involucradas
    - Si necesita más información
    - Complejidad inicial
    """
    logger.info("Nodo: classify")

    # Tomar el último mensaje del usuario
    last_message = ""
    for msg in reversed(state.messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_message = msg.content
            break

    problem = state.user_problem or last_message

    prompt = CLASSIFY_PROMPT.format(problem=problem)
    llm = get_llm()

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        # Extraer JSON de la respuesta
        content = response.content
        # Limpiar markdown si viene envuelto en ```json
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())

        return {
            "detected_areas": result.get("areas", ["civil"]),
            "pending_questions": result.get("clarification_questions", []),
            "complexity": result.get("initial_complexity", "moderate"),
            "user_problem": problem,
        }

    except Exception as e:
        logger.error(f"Error en classify_node: {e}")
        return {
            "detected_areas": ["civil"],
            "pending_questions": [],
            "complexity": "moderate",
            "user_problem": problem,
        }

"""
Nodo 3: Graph RAG — recupera leyes relevantes de ChromaDB + Neo4j.
"""

from loguru import logger
from backend.agent.state import AgentState
from data_engineering.retrieval.hybrid_retriever import retrieve


def retrieve_node(state: AgentState) -> dict:
    """
    Ejecuta el Hybrid Retriever (ChromaDB + Neo4j + CrossEncoder)
    y enriquece el estado con contexto legal relevante.
    """
    logger.info(f"Nodo: retrieve | áreas: {state.detected_areas}")

    result = retrieve(
        query=state.user_problem,
        ciudad=state.user_city,
    )

    return {
        "legal_context": result.build_context_string(),
        "suggested_processes": result.processes,
        "suggested_lawyers": result.lawyers,
        "detected_areas": result.detected_areas or state.detected_areas,
    }

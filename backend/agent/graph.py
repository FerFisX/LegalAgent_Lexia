"""
Grafo LangGraph del agente legal Lexia.

Flujo de estados:
  START
    │
    ▼
  classify ──────────────────────────────────────┐
    │                                             │
    ▼                                             │
  ¿necesita clarificación?                        │
    │ SÍ (y < max_rounds)    │ NO                │
    ▼                        ▼                   │
  clarify              retrieve                   │
    │                        │                   │
    └──────► (espera        evaluate              │
              respuesta)     │                   │
                             │                   │
                    ¿complejo?                    │
                    │ SÍ          │ NO            │
                    ▼             ▼               │
              refer_lawyer     respond            │
                    │             │               │
                    └──────┬──────┘               │
                           ▼                      │
                          END ◄───────────────────┘
"""

from langgraph.graph import StateGraph, END

from backend.agent.state import AgentState
from backend.agent.nodes.classify import classify_node
from backend.agent.nodes.clarify import clarify_node
from backend.agent.nodes.retrieve import retrieve_node
from backend.agent.nodes.evaluate import evaluate_node
from backend.agent.nodes.respond import respond_node, refer_lawyer_node


# ── Funciones de decisión (edges condicionales) ───────────────────────────────

def should_clarify(state: AgentState) -> str:
    """
    Decide si hacer preguntas de clarificación o proceder al RAG.
    """
    needs_clarification = bool(state.pending_questions)
    under_max_rounds = state.clarification_rounds < state.max_clarification_rounds

    if needs_clarification and under_max_rounds:
        return "clarify"
    return "retrieve"


def should_refer_or_respond(state: AgentState) -> str:
    """
    Decide si responder directamente o derivar a abogado.
    """
    if state.needs_lawyer or state.complexity == "complex":
        return "refer_lawyer"
    return "respond"


# ── Construcción del grafo ────────────────────────────────────────────────────

def build_agent() -> StateGraph:
    graph = StateGraph(AgentState)

    # Registrar nodos
    graph.add_node("classify", classify_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("respond", respond_node)
    graph.add_node("refer_lawyer", refer_lawyer_node)

    # Edge de entrada
    graph.set_entry_point("classify")

    # Edge condicional: classify → clarify OR retrieve
    graph.add_conditional_edges(
        "classify",
        should_clarify,
        {
            "clarify": "clarify",
            "retrieve": "retrieve",
        },
    )

    # Después de clarificar: volver a clasificar con más contexto
    graph.add_edge("clarify", END)  # espera respuesta del usuario

    # retrieve → evaluate
    graph.add_edge("retrieve", "evaluate")

    # Edge condicional: evaluate → respond OR refer_lawyer
    graph.add_conditional_edges(
        "evaluate",
        should_refer_or_respond,
        {
            "respond": "respond",
            "refer_lawyer": "refer_lawyer",
        },
    )

    # Nodos finales
    graph.add_edge("respond", END)
    graph.add_edge("refer_lawyer", END)

    return graph.compile()


# Instancia compilada (singleton)
agent_graph = build_agent()

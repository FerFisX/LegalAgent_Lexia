"""
Fixtures compartidas para toda la suite de pruebas de Lexia.

Usa SQLite en memoria para no necesitar PostgreSQL en los tests.
El agente LangGraph se mockea para no depender de Ollama/Gemini.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from backend.core.database import Base, get_db
from backend.main import app


# ── Base de datos en memoria (SQLite) ─────────────────────────────────────────
TEST_DB_URL = "sqlite:///./test_lexia.db"

engine_test = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Crea todas las tablas antes de correr los tests y las elimina al final."""
    # Importar modelos para que Base los registre
    from backend.models import User, Conversation, Message  # noqa: F401
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture()
def db():
    """Sesión de base de datos aislada para cada test (con rollback al final)."""
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """
    Cliente HTTP de FastAPI con la DB de test inyectada.
    El agente LangGraph está mockeado para no llamar al LLM real.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Mock del agente para no necesitar Ollama
    mock_agent_result = {
        "final_response": "Respuesta de prueba del agente legal.",
        "detected_areas": ["laboral"],
        "complexity": "simple",
        "suggested_lawyers": [],
        "suggested_processes": [],
        "needs_lawyer": False,
        "messages": [MagicMock(content="Respuesta de prueba del agente legal.")],
    }

    with patch("backend.services.chat_service.agent_graph") as mock_graph:
        mock_graph.invoke.return_value = mock_agent_result
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


# ── Helpers de fixtures ───────────────────────────────────────────────────────

@pytest.fixture()
def registered_user(client):
    """Crea un usuario registrado y retorna sus datos + token."""
    resp = client.post("/auth/signup", json={
        "email": "test@lexia.bo",
        "username": "TestUser",
        "password": "password123",
    })
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
def auth_headers(registered_user):
    """Headers de autorización para el usuario registrado."""
    return {"Authorization": f"Bearer {registered_user['access_token']}"}


@pytest.fixture()
def guest_token(client):
    """Token de sesión de invitado."""
    resp = client.post("/auth/guest")
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture()
def guest_headers(guest_token):
    """Headers de autorización para el invitado."""
    return {"Authorization": f"Bearer {guest_token}"}

"""
PRUEBAS UNITARIAS — Modelos ORM y Schemas Pydantic
Cubre: User, Conversation, Message, SignupRequest, LoginRequest, ChatRequest
"""

import pytest
from pydantic import ValidationError
from backend.schemas.auth import SignupRequest, LoginRequest, TokenResponse
from backend.schemas.chat import ChatRequest


class TestSignupRequest:
    """Tests para el schema de registro."""

    def test_valida_datos_correctos(self):
        data = SignupRequest(
            email="usuario@lexia.bo",
            username="JuanMamani",
            password="segura123",
        )
        assert data.email == "usuario@lexia.bo"
        assert data.username == "JuanMamani"

    def test_rechaza_email_invalido(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="no_es_email", username="Juan", password="pass123")

    def test_rechaza_email_vacio(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="", username="Juan", password="pass123")

    def test_requiere_todos_los_campos(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com")  # falta username y password

    def test_acepta_email_con_subdominios(self):
        data = SignupRequest(
            email="usuario@correo.gob.bo",
            username="Funcionario",
            password="pass123",
        )
        assert "@" in data.email


class TestLoginRequest:
    """Tests para el schema de login."""

    def test_valida_datos_correctos(self):
        data = LoginRequest(email="test@test.bo", password="mipass")
        assert data.email == "test@test.bo"

    def test_rechaza_email_invalido(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="no_email", password="pass")

    def test_requiere_password(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="test@test.bo")


class TestTokenResponse:
    """Tests para el schema de respuesta de token."""

    def test_crea_token_response_minimo(self):
        data = TokenResponse(
            access_token="jwt.token.aqui",
            user_id="uuid-1234",
        )
        assert data.token_type == "bearer"
        assert data.is_guest is False

    def test_token_response_invitado(self):
        data = TokenResponse(
            access_token="jwt.token.aqui",
            user_id="uuid-5678",
            is_guest=True,
            guest_queries_remaining=3,
        )
        assert data.is_guest is True
        assert data.guest_queries_remaining == 3


class TestChatRequest:
    """Tests para el schema de solicitud de chat."""

    def test_valida_mensaje_simple(self):
        data = ChatRequest(message="Me despidieron sin causa")
        assert data.message == "Me despidieron sin causa"
        assert data.conversation_id is None

    def test_acepta_conversation_id_opcional(self):
        data = ChatRequest(
            message="segunda consulta",
            conversation_id="conv-uuid-001",
        )
        assert data.conversation_id == "conv-uuid-001"

    def test_requiere_campo_message(self):
        with pytest.raises(ValidationError):
            ChatRequest()  # sin mensaje

    def test_acepta_mensaje_largo(self):
        mensaje_largo = "a" * 2000
        data = ChatRequest(message=mensaje_largo)
        assert len(data.message) == 2000


class TestUserModel:
    """Tests para el modelo ORM User usando la DB de test."""

    def test_crea_usuario_registrado(self, db):
        from backend.models.user import User
        import uuid
        user = User(
            id=str(uuid.uuid4()),
            email="nuevo@lexia.bo",
            username="NuevoUsuario",
            hashed_password="$2b$12$fakehash",
            is_guest=False,
        )
        db.add(user)
        db.flush()

        found = db.query(User).filter(User.email == "nuevo@lexia.bo").first()
        assert found is not None
        assert found.username == "NuevoUsuario"
        assert found.is_guest is False
        assert found.guest_query_count == 0

    def test_crea_usuario_invitado(self, db):
        from backend.models.user import User
        import uuid
        guest = User(
            id=str(uuid.uuid4()),
            is_guest=True,
            guest_query_count=0,
        )
        db.add(guest)
        db.flush()

        found = db.query(User).filter(User.id == guest.id).first()
        assert found.is_guest is True
        assert found.email is None
        assert found.username is None

    def test_incrementa_contador_invitado(self, db):
        from backend.models.user import User
        import uuid
        guest = User(id=str(uuid.uuid4()), is_guest=True, guest_query_count=0)
        db.add(guest)
        db.flush()

        guest.guest_query_count += 1
        db.flush()

        found = db.query(User).filter(User.id == guest.id).first()
        assert found.guest_query_count == 1


class TestConversationModel:
    """Tests para el modelo ORM Conversation."""

    def test_crea_conversacion(self, db):
        from backend.models.user import User
        from backend.models.conversation import Conversation
        import uuid

        user = User(id=str(uuid.uuid4()), email="conv@test.bo", username="ConvUser",
                    hashed_password="hash", is_guest=False)
        db.add(user)
        db.flush()

        conv = Conversation(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title="Consulta sobre despido",
        )
        db.add(conv)
        db.flush()

        found = db.query(Conversation).filter(Conversation.user_id == user.id).first()
        assert found is not None
        assert found.title == "Consulta sobre despido"
        assert found.status == "active"

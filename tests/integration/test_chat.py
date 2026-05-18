"""
PRUEBAS DE INTEGRACIÓN — Endpoints de chat
Cubre: POST /chat, GET /chat/conversations, GET /chat/{id}

El agente LangGraph está mockeado (ver conftest.py) para no necesitar Ollama.
"""

import pytest


class TestEnviarMensaje:
    """Tests para POST /chat."""

    def test_usuario_registrado_puede_chatear(self, client, auth_headers):
        resp = client.post("/chat", json={"message": "Me despidieron sin causa"}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "conversation_id" in body
        assert "message" in body
        assert body["message"]["content"] != ""

    def test_respuesta_incluye_metadatos(self, client, auth_headers):
        resp = client.post("/chat", json={"message": "Tuve un accidente"}, headers=auth_headers)
        body = resp.json()
        assert "detected_areas" in body
        assert "complexity" in body
        assert "suggested_lawyers" in body
        assert "suggested_processes" in body

    def test_invitado_puede_chatear(self, client, guest_headers):
        resp = client.post("/chat", json={"message": "Consulta laboral"}, headers=guest_headers)
        assert resp.status_code == 200

    def test_sin_token_retorna_401(self, client):
        resp = client.post("/chat", json={"message": "Consulta sin auth"})
        assert resp.status_code == 401

    def test_mensaje_vacio_retorna_400(self, client, auth_headers):
        resp = client.post("/chat", json={"message": "   "}, headers=auth_headers)
        assert resp.status_code == 400

    def test_mensaje_vacio_string_retorna_400(self, client, auth_headers):
        resp = client.post("/chat", json={"message": ""}, headers=auth_headers)
        assert resp.status_code in (400, 422)

    def test_genera_conversation_id_en_primer_mensaje(self, client, auth_headers):
        resp = client.post("/chat", json={"message": "Primera consulta"}, headers=auth_headers)
        body = resp.json()
        assert body["conversation_id"] is not None
        assert len(body["conversation_id"]) > 0

    def test_continua_conversacion_existente(self, client, auth_headers):
        """Un segundo mensaje con conversation_id debe continuar la misma conversación."""
        resp1 = client.post("/chat", json={"message": "Primera consulta"}, headers=auth_headers)
        conv_id = resp1.json()["conversation_id"]

        resp2 = client.post("/chat",
            json={"message": "Segunda pregunta", "conversation_id": conv_id},
            headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["conversation_id"] == conv_id

    def test_conversation_id_invalido_crea_nueva_conversacion(self, client, auth_headers):
        """Si el conversation_id no existe, debe crear una nueva conversación."""
        resp = client.post("/chat",
            json={"message": "Mensaje", "conversation_id": "uuid-que-no-existe"},
            headers=auth_headers)
        assert resp.status_code == 200
        # Debe crear una nueva conversación
        assert resp.json()["conversation_id"] != "uuid-que-no-existe"


class TestListarConversaciones:
    """Tests para GET /chat/conversations."""

    def test_usuario_nuevo_tiene_lista_vacia(self, client):
        # Crear usuario nuevo sin conversaciones
        client.post("/auth/signup", json={
            "email": "sinconvs@lexia.bo",
            "username": "SinConvs",
            "password": "pass123",
        })
        resp_login = client.post("/auth/login", json={
            "email": "sinconvs@lexia.bo",
            "password": "pass123",
        })
        token = resp_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/chat/conversations", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lista_conversaciones_tras_chatear(self, client, auth_headers):
        client.post("/chat", json={"message": "Consulta 1"}, headers=auth_headers)
        client.post("/chat", json={"message": "Consulta 2"}, headers=auth_headers)

        resp = client.get("/chat/conversations", headers=auth_headers)
        assert resp.status_code == 200
        convs = resp.json()
        assert len(convs) >= 2

    def test_sin_token_retorna_401(self, client):
        resp = client.get("/chat/conversations")
        assert resp.status_code == 401

    def test_conversacion_tiene_campos_requeridos(self, client, auth_headers):
        client.post("/chat", json={"message": "Consulta de prueba"}, headers=auth_headers)
        resp = client.get("/chat/conversations", headers=auth_headers)
        conv = resp.json()[0]
        assert "id" in conv
        assert "title" in conv
        assert "status" in conv


class TestObtenerConversacion:
    """Tests para GET /chat/{conversation_id}."""

    def test_obtiene_conversacion_existente(self, client, auth_headers):
        # Crear conversación
        resp_chat = client.post("/chat", json={"message": "Consulta laboral"}, headers=auth_headers)
        conv_id = resp_chat.json()["conversation_id"]

        resp = client.get(f"/chat/{conv_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == conv_id

    def test_conversacion_incluye_mensajes(self, client, auth_headers):
        resp_chat = client.post("/chat", json={"message": "Mi consulta"}, headers=auth_headers)
        conv_id = resp_chat.json()["conversation_id"]

        resp = client.get(f"/chat/{conv_id}", headers=auth_headers)
        body = resp.json()
        assert "messages" in body
        assert len(body["messages"]) >= 2  # user + assistant

    def test_conversacion_inexistente_retorna_404(self, client, auth_headers):
        resp = client.get("/chat/id-que-no-existe", headers=auth_headers)
        assert resp.status_code == 404

    def test_no_puede_ver_conversacion_de_otro_usuario(self, client, auth_headers):
        """Un usuario no debe poder acceder a conversaciones de otro."""
        # Crear conversación con usuario 1
        resp_chat = client.post("/chat", json={"message": "Conversación privada"}, headers=auth_headers)
        conv_id = resp_chat.json()["conversation_id"]

        # Crear usuario 2 y obtener sus headers
        client.post("/auth/signup", json={
            "email": "otro2@lexia.bo", "username": "Otro2", "password": "pass123"
        })
        resp_login2 = client.post("/auth/login", json={
            "email": "otro2@lexia.bo", "password": "pass123"
        })
        headers2 = {"Authorization": f"Bearer {resp_login2.json()['access_token']}"}

        resp = client.get(f"/chat/{conv_id}", headers=headers2)
        assert resp.status_code == 404

    def test_sin_token_retorna_401(self, client):
        resp = client.get("/chat/cualquier-id")
        assert resp.status_code == 401

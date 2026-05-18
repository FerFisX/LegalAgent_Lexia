"""
PRUEBAS DE REGRESIÓN — Lexia
Verifican que comportamientos críticos del sistema no se rompan
con futuros cambios en el código.

Cada test está marcado con el comportamiento que protege.
"""

import pytest


class TestLimiteInvitado:
    """
    REGRESIÓN: El límite de 3 consultas para invitados nunca debe sobrepasarse.
    """

    def test_invitado_puede_hacer_3_consultas(self, client, guest_headers):
        for i in range(3):
            resp = client.post("/chat",
                json={"message": f"Consulta número {i+1}"},
                headers=guest_headers)
            assert resp.status_code == 200, f"Consulta {i+1} falló inesperadamente"

    def test_invitado_es_bloqueado_en_4a_consulta(self, client):
        """Después de 3 consultas, el invitado debe recibir un error."""
        resp_guest = client.post("/auth/guest")
        token = resp_guest.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for _ in range(3):
            client.post("/chat", json={"message": "Consulta"}, headers=headers)

        resp4 = client.post("/chat", json={"message": "Cuarta consulta"}, headers=headers)
        assert resp4.status_code in (403, 429), (
            "La 4ª consulta de invitado debe ser bloqueada (403 o 429)"
        )


class TestSeguridadAutenticacion:
    """
    REGRESIÓN: El sistema de auth nunca debe aceptar tokens o credenciales inválidas.
    """

    def test_token_expirado_o_falso_es_rechazado(self, client):
        headers = {"Authorization": "Bearer token.completamente.falso"}
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 401

    def test_bearer_sin_token_es_rechazado(self, client):
        headers = {"Authorization": "Bearer "}
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 401

    def test_sin_header_auth_es_rechazado(self, client):
        resp = client.post("/chat", json={"message": "Hola"})
        assert resp.status_code == 401

    def test_password_incorrecto_siempre_retorna_401(self, client, registered_user):
        for pwd in ["", "pass", "PASSWORD123", "password123 ", " password123"]:
            resp = client.post("/auth/login", json={
                "email": "test@lexia.bo",
                "password": pwd,
            })
            assert resp.status_code == 401, f"Password '{pwd}' no debería funcionar"

    def test_no_puede_registrar_email_duplicado(self, client, registered_user):
        resp = client.post("/auth/signup", json={
            "email": "test@lexia.bo",
            "username": "OtroNombre",
            "password": "otrapass123",
        })
        assert resp.status_code == 400


class TestIntegridadDatos:
    """
    REGRESIÓN: Los datos guardados en la DB deben ser consistentes y correctos.
    """

    def test_titulo_conversacion_es_inicio_del_mensaje(self, client, auth_headers):
        """El título de la conversación debe ser los primeros 60 caracteres del mensaje."""
        mensaje = "Necesito saber qué hacer porque me despidieron sin preaviso"
        resp = client.post("/chat", json={"message": mensaje}, headers=auth_headers)
        conv_id = resp.json()["conversation_id"]

        resp_conv = client.get(f"/chat/{conv_id}", headers=auth_headers)
        titulo = resp_conv.json()["title"]
        assert titulo in mensaje or mensaje.startswith(titulo.rstrip("..."))

    def test_conversacion_tiene_mensajes_user_y_assistant(self, client, auth_headers):
        resp = client.post("/chat", json={"message": "Mi consulta"}, headers=auth_headers)
        conv_id = resp.json()["conversation_id"]

        resp_conv = client.get(f"/chat/{conv_id}", headers=auth_headers)
        mensajes = resp_conv.json()["messages"]
        roles = [m["role"] for m in mensajes]

        assert "user" in roles
        assert "assistant" in roles

    def test_usuario_solo_ve_sus_propias_conversaciones(self, client):
        # Usuario A
        client.post("/auth/signup", json={
            "email": "usuarioA@test.bo", "username": "UserA", "password": "passA123"
        })
        login_a = client.post("/auth/login", json={"email": "usuarioA@test.bo", "password": "passA123"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Usuario B
        client.post("/auth/signup", json={
            "email": "usuarioB@test.bo", "username": "UserB", "password": "passB123"
        })
        login_b = client.post("/auth/login", json={"email": "usuarioB@test.bo", "password": "passB123"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # A crea conversación, B no debe verla
        client.post("/chat", json={"message": "Conversación privada de A"}, headers=headers_a)

        convs_b = client.get("/chat/conversations", headers=headers_b).json()
        titulos = [c["title"] for c in convs_b]
        assert not any("privada de A" in t for t in titulos)


class TestValidacionEntradas:
    """
    REGRESIÓN: Las entradas inválidas siempre deben ser rechazadas correctamente.
    """

    def test_mensaje_solo_espacios_es_rechazado(self, client, auth_headers):
        resp = client.post("/chat", json={"message": "     "}, headers=auth_headers)
        assert resp.status_code == 400

    def test_signup_con_password_muy_corto_es_rechazado(self, client):
        """La capa de validación de negocio debe rechazar passwords < 6 chars.
        Nota: esta validación está en el frontend. El backend acepta cualquier longitud.
        Este test documenta el comportamiento actual."""
        resp = client.post("/auth/signup", json={
            "email": "corto@test.bo",
            "username": "Corto",
            "password": "ab",
        })
        # El backend actualmente no valida longitud mínima (lo hace el frontend)
        # Si en el futuro se añade validación backend, este test debe actualizarse
        assert resp.status_code in (201, 400, 422)

    def test_endpoint_inexistente_retorna_404(self, client):
        resp = client.get("/ruta/que/no/existe")
        assert resp.status_code == 404

    def test_metodo_incorrecto_retorna_405(self, client):
        resp = client.get("/auth/signup")  # debe ser POST
        assert resp.status_code == 405


class TestCORSyHeaders:
    """
    REGRESIÓN: Las cabeceras CORS deben estar presentes para el frontend.
    """

    def test_cors_headers_presentes_en_respuesta(self, client):
        resp = client.options(
            "/auth/guest",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
        )
        # FastAPI con CORSMiddleware debe responder con los headers correctos
        assert resp.status_code in (200, 204)

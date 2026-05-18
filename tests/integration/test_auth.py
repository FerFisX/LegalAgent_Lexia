"""
PRUEBAS DE INTEGRACIÓN — Endpoints de autenticación
Cubre: POST /auth/signup, POST /auth/login, POST /auth/guest, GET /auth/me
"""

import pytest


class TestSignup:
    """Pruebas de integración para el registro de usuarios."""

    def test_registro_exitoso_retorna_201_y_token(self, client):
        resp = client.post("/auth/signup", json={
            "email": "nuevo@lexia.bo",
            "username": "NuevoUsuario",
            "password": "password123",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["is_guest"] is False
        assert body["username"] == "NuevoUsuario"

    def test_registro_retorna_user_id(self, client):
        resp = client.post("/auth/signup", json={
            "email": "otro@lexia.bo",
            "username": "OtroUsuario",
            "password": "password123",
        })
        body = resp.json()
        assert "user_id" in body
        assert len(body["user_id"]) > 0

    def test_email_duplicado_retorna_400(self, client):
        payload = {
            "email": "duplicado@lexia.bo",
            "username": "Usuario1",
            "password": "password123",
        }
        client.post("/auth/signup", json=payload)
        resp2 = client.post("/auth/signup", json=payload)
        assert resp2.status_code == 400
        assert "registrado" in resp2.json()["detail"].lower()

    def test_email_invalido_retorna_422(self, client):
        resp = client.post("/auth/signup", json={
            "email": "no_es_email",
            "username": "Usuario",
            "password": "password123",
        })
        assert resp.status_code == 422

    def test_campos_faltantes_retorna_422(self, client):
        resp = client.post("/auth/signup", json={"email": "a@b.com"})
        assert resp.status_code == 422


class TestLogin:
    """Pruebas de integración para el login de usuarios."""

    def test_login_exitoso_retorna_token(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "email": "test@lexia.bo",
            "password": "password123",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["is_guest"] is False

    def test_password_incorrecto_retorna_401(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "email": "test@lexia.bo",
            "password": "password_incorrecto",
        })
        assert resp.status_code == 401
        assert "credenciales" in resp.json()["detail"].lower()

    def test_email_no_registrado_retorna_401(self, client):
        resp = client.post("/auth/login", json={
            "email": "noexiste@lexia.bo",
            "password": "cualquier_pass",
        })
        assert resp.status_code == 401

    def test_login_retorna_username_correcto(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "email": "test@lexia.bo",
            "password": "password123",
        })
        assert resp.json()["username"] == "TestUser"


class TestGuestSession:
    """Pruebas de integración para sesiones de invitado."""

    def test_guest_retorna_201_y_token(self, client):
        resp = client.post("/auth/guest")
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["is_guest"] is True

    def test_guest_retorna_consultas_restantes(self, client):
        resp = client.post("/auth/guest")
        body = resp.json()
        assert "guest_queries_remaining" in body
        assert body["guest_queries_remaining"] == 3  # GUEST_MAX_QUERIES

    def test_cada_guest_tiene_id_unico(self, client):
        resp1 = client.post("/auth/guest")
        resp2 = client.post("/auth/guest")
        assert resp1.json()["user_id"] != resp2.json()["user_id"]

    def test_guest_no_requiere_body(self, client):
        """El endpoint de guest no necesita ningún parámetro."""
        resp = client.post("/auth/guest")
        assert resp.status_code == 201


class TestGetMe:
    """Pruebas de integración para el perfil del usuario autenticado."""

    def test_me_retorna_datos_del_usuario(self, client, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "test@lexia.bo"
        assert body["username"] == "TestUser"
        assert body["is_guest"] is False

    def test_me_sin_token_retorna_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_con_token_invalido_retorna_401(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer token.falso.aqui"})
        assert resp.status_code == 401

    def test_me_invitado_retorna_is_guest_true(self, client, guest_headers):
        resp = client.get("/auth/me", headers=guest_headers)
        assert resp.status_code == 200
        assert resp.json()["is_guest"] is True

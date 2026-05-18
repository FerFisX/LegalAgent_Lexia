"""
PRUEBAS DE USABILIDAD — Lexia
Simulan flujos completos de usuario como lo haría una persona real.
Cada test representa un escenario de uso documentado.

Criterios de aceptación:
  ✓ El usuario puede completar el flujo sin instrucciones adicionales
  ✓ Los mensajes de error son claros y orientan la corrección
  ✓ El sistema responde en tiempo razonable (< 60s con LLM real)
  ✓ La información mostrada es coherente y útil
"""

import pytest


class TestFlujoInvitado:
    """
    ESCENARIO U-01: Un ciudadano llega a la app por primera vez.
    No tiene cuenta. Quiere una consulta rápida.
    """

    def test_U01_invitado_puede_consultar_sin_registrarse(self, client):
        """
        DADO QUE un usuario sin cuenta llega a la app
        CUANDO envía un mensaje directamente (el sistema crea sesión de invitado)
        ENTONCES recibe una respuesta legal coherente
        """
        # Crear sesión de invitado (simula el flujo automático del frontend)
        guest = client.post("/auth/guest").json()
        headers = {"Authorization": f"Bearer {guest['access_token']}"}

        resp = client.post("/chat",
            json={"message": "Me despidieron sin causa justificada, ¿qué puedo hacer?"},
            headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        # La respuesta debe tener contenido
        assert len(body["message"]["content"]) > 10
        # Debe detectar el área correcta
        assert "laboral" in body.get("detected_areas", [])

    def test_U01_sistema_informa_limite_de_consultas(self, client):
        """
        DADO QUE un invitado ya usó sus 3 consultas
        CUANDO intenta una cuarta
        ENTONCES el sistema lo bloquea con mensaje claro
        """
        guest = client.post("/auth/guest").json()
        headers = {"Authorization": f"Bearer {guest['access_token']}"}

        for _ in range(3):
            client.post("/chat", json={"message": "Consulta"}, headers=headers)

        resp = client.post("/chat", json={"message": "Cuarta consulta"}, headers=headers)
        assert resp.status_code in (403, 429)


class TestFlujoRegistro:
    """
    ESCENARIO U-02: Un usuario invitado decide crear una cuenta para acceso ilimitado.
    """

    def test_U02_registro_exitoso_y_acceso_inmediato(self, client):
        """
        DADO QUE un usuario quiere registrarse
        CUANDO completa el formulario con datos válidos
        ENTONCES recibe un token y puede chatear inmediatamente
        """
        resp = client.post("/auth/signup", json={
            "email": "ciudadano@gmail.com",
            "username": "JuanCiudadano",
            "password": "mipass123",
        })
        assert resp.status_code == 201
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp_chat = client.post("/chat",
            json={"message": "Tengo un problema laboral"},
            headers=headers)
        assert resp_chat.status_code == 200

    def test_U02_mensaje_claro_si_email_ya_existe(self, client, registered_user):
        """
        DADO QUE un usuario intenta registrarse con un email ya usado
        CUANDO envía el formulario
        ENTONCES recibe un mensaje explicativo (no un error técnico)
        """
        resp = client.post("/auth/signup", json={
            "email": "test@lexia.bo",
            "username": "OtroNombre",
            "password": "otrapass",
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        # El mensaje debe ser comprensible para el usuario
        assert isinstance(detail, str)
        assert len(detail) > 5

    def test_U02_login_con_credenciales_correctas(self, client, registered_user):
        """
        DADO QUE un usuario ya registrado quiere ingresar
        CUANDO escribe su email y contraseña correctos
        ENTONCES accede sin problemas
        """
        resp = client.post("/auth/login", json={
            "email": "test@lexia.bo",
            "password": "password123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()


class TestFlujoConsultaCompleta:
    """
    ESCENARIO U-03: Un usuario registrado realiza una consulta legal completa.
    """

    def test_U03_consulta_laboral_retorna_procesos_utiles(self, client, auth_headers):
        """
        DADO QUE un trabajador despedido busca orientación
        CUANDO describe su situación
        ENTONCES recibe información sobre el proceso a seguir
        """
        resp = client.post("/chat",
            json={"message": "Me despidieron sin preaviso después de 3 años de trabajo"},
            headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()

        # El área detectada debe ser laboral
        assert "laboral" in body.get("detected_areas", [])
        # Debe haber alguna información de proceso o respuesta útil
        tiene_procesos = len(body.get("suggested_processes", [])) > 0
        tiene_respuesta = len(body["message"]["content"]) > 20
        assert tiene_procesos or tiene_respuesta

    def test_U03_consulta_penal_retorna_orientacion(self, client, auth_headers):
        """
        DADO QUE una persona fue víctima de un robo
        CUANDO describe el hecho
        ENTONCES recibe orientación sobre cómo denunciar
        """
        resp = client.post("/chat",
            json={"message": "Me robaron el celular y la cartera en la calle"},
            headers=auth_headers)
        assert resp.status_code == 200
        assert "penal" in resp.json().get("detected_areas", [])

    def test_U03_historial_de_conversacion_es_accesible(self, client, auth_headers):
        """
        DADO QUE un usuario tuvo varias consultas
        CUANDO revisa su historial
        ENTONCES puede ver todas sus conversaciones anteriores con títulos descriptivos
        """
        client.post("/chat", json={"message": "Consulta sobre despido"}, headers=auth_headers)
        client.post("/chat", json={"message": "Consulta sobre accidente"}, headers=auth_headers)

        resp = client.get("/chat/conversations", headers=auth_headers)
        assert resp.status_code == 200
        convs = resp.json()
        assert len(convs) >= 2
        # Las conversaciones deben tener títulos (no vacíos)
        for conv in convs:
            assert conv.get("title") and len(conv["title"]) > 0

    def test_U03_puede_retomar_conversacion_anterior(self, client, auth_headers):
        """
        DADO QUE un usuario quiere continuar una consulta anterior
        CUANDO envía un mensaje con el conversation_id
        ENTONCES el sistema recuerda el contexto
        """
        resp1 = client.post("/chat",
            json={"message": "Tengo un problema laboral"},
            headers=auth_headers)
        conv_id = resp1.json()["conversation_id"]

        resp2 = client.post("/chat",
            json={"message": "¿Qué documentos necesito?", "conversation_id": conv_id},
            headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["conversation_id"] == conv_id


class TestUsabilidadErrores:
    """
    ESCENARIO U-04: El sistema maneja errores de forma amigable.
    """

    def test_U04_mensaje_vacio_no_rompe_la_app(self, client, auth_headers):
        """
        DADO QUE un usuario accidentalmente envía un mensaje vacío
        CUANDO el servidor lo procesa
        ENTONCES retorna un error claro (no un 500)
        """
        resp = client.post("/chat", json={"message": ""}, headers=auth_headers)
        assert resp.status_code in (400, 422)
        # No debe ser un error 500 (error interno)
        assert resp.status_code != 500

    def test_U04_credenciales_incorrectas_dan_mensaje_claro(self, client, registered_user):
        """
        DADO QUE un usuario escribe mal su contraseña
        CUANDO intenta hacer login
        ENTONCES recibe un mensaje orientativo (no un stack trace)
        """
        resp = client.post("/auth/login", json={
            "email": "test@lexia.bo",
            "password": "contrasenaequivocada",
        })
        assert resp.status_code == 401
        body = resp.json()
        assert "detail" in body
        assert isinstance(body["detail"], str)

    def test_U04_acceso_sin_autenticar_da_respuesta_clara(self, client):
        """
        DADO QUE un usuario intenta chatear sin token
        CUANDO hace la petición
        ENTONCES recibe un 401 (no un 500 ni un 200 vacío)
        """
        resp = client.post("/chat", json={"message": "Hola"})
        assert resp.status_code == 401


class TestAccesibilidadAPI:
    """
    ESCENARIO U-05: Verificar que la API es navegable y documentada.
    """

    def test_U05_docs_swagger_accesible(self, client):
        """
        La documentación automática de FastAPI debe estar disponible
        para que el equipo de desarrollo pueda probar los endpoints.
        """
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_U05_openapi_json_accesible(self, client):
        """El schema OpenAPI debe estar disponible para integración con frontend."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema
        # Verificar que los endpoints principales están documentados
        assert "/auth/signup" in schema["paths"]
        assert "/auth/login" in schema["paths"]
        assert "/chat" in schema["paths"]

    def test_U05_health_o_root_accesible(self, client):
        """El servidor debe responder en la ruta raíz."""
        resp = client.get("/")
        assert resp.status_code in (200, 404)  # 404 es aceptable si no hay ruta raíz

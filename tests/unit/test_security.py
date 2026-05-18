"""
PRUEBAS UNITARIAS — Módulo de seguridad
Cubre: hash_password, verify_password, create_access_token, decode_token
"""

import pytest
import time
from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)


class TestHashPassword:
    """Tests para la función hash_password."""

    def test_genera_hash_diferente_al_texto_original(self):
        """El hash no debe ser igual a la contraseña en texto plano."""
        hashed = hash_password("micontraseña123")
        assert hashed != "micontraseña123"

    def test_hash_empieza_con_prefijo_bcrypt(self):
        """bcrypt siempre genera hashes que empiezan con $2b$."""
        hashed = hash_password("cualquier_pass")
        assert hashed.startswith("$2b$")

    def test_dos_hashes_del_mismo_password_son_distintos(self):
        """bcrypt usa salt aleatorio, así que dos hashes del mismo password difieren."""
        h1 = hash_password("mismo_password")
        h2 = hash_password("mismo_password")
        assert h1 != h2

    def test_hash_de_password_vacio(self):
        """Debe poder hashear una cadena vacía sin error."""
        hashed = hash_password("")
        assert hashed.startswith("$2b$")

    def test_hash_de_password_con_caracteres_especiales(self):
        """Debe manejar caracteres especiales y acentos."""
        hashed = hash_password("contraseña_ñoña_@#$%")
        assert hashed.startswith("$2b$")


class TestVerifyPassword:
    """Tests para la función verify_password."""

    def test_verifica_correctamente_password_valido(self):
        """La verificación debe retornar True cuando el password es correcto."""
        hashed = hash_password("password_correcto")
        assert verify_password("password_correcto", hashed) is True

    def test_rechaza_password_incorrecto(self):
        """Debe retornar False cuando el password no coincide."""
        hashed = hash_password("password_correcto")
        assert verify_password("password_incorrecto", hashed) is False

    def test_rechaza_password_similar(self):
        """Debe rechazar passwords similares pero no idénticos."""
        hashed = hash_password("Password123")
        assert verify_password("password123", hashed) is False  # case sensitive

    def test_verifica_password_vacio(self):
        """La verificación de cadena vacía contra su hash debe ser True."""
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_rechaza_hash_invalido(self):
        """Debe manejar un hash malformado sin lanzar excepción."""
        result = verify_password("cualquier", "hash_invalido_que_no_es_bcrypt")
        assert result is False


class TestCreateAccessToken:
    """Tests para la función create_access_token."""

    def test_genera_un_string_no_vacio(self):
        """El token debe ser una cadena no vacía."""
        token = create_access_token({"sub": "user123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_tiene_formato_jwt_tres_partes(self):
        """Un JWT válido tiene exactamente 3 partes separadas por punto."""
        token = create_access_token({"sub": "user123"})
        partes = token.split(".")
        assert len(partes) == 3

    def test_diferentes_payloads_generan_tokens_distintos(self):
        """Dos payloads distintos deben producir tokens distintos."""
        t1 = create_access_token({"sub": "user1"})
        t2 = create_access_token({"sub": "user2"})
        assert t1 != t2

    def test_mismo_payload_en_distinto_momento_genera_tokens_distintos(self):
        """El campo 'exp' cambia con el tiempo, así que los tokens difieren."""
        t1 = create_access_token({"sub": "user1"})
        time.sleep(1)
        t2 = create_access_token({"sub": "user1"})
        assert t1 != t2


class TestDecodeToken:
    """Tests para la función decode_token."""

    def test_decodifica_token_valido(self):
        """Debe retornar el payload original al decodificar un token válido."""
        token = create_access_token({"sub": "abc123", "email": "test@test.bo"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "abc123"
        assert payload["email"] == "test@test.bo"

    def test_retorna_none_para_token_invalido(self):
        """Un token malformado debe retornar None sin lanzar excepción."""
        result = decode_token("esto.no.es.un.jwt")
        assert result is None

    def test_retorna_none_para_cadena_vacia(self):
        """Una cadena vacía debe retornar None."""
        result = decode_token("")
        assert result is None

    def test_retorna_none_para_token_firmado_con_otra_clave(self):
        """Un token firmado con una clave secreta diferente debe ser rechazado."""
        from jose import jwt
        token_falso = jwt.encode(
            {"sub": "hacker", "exp": 9999999999},
            "clave_secreta_falsa",
            algorithm="HS256",
        )
        result = decode_token(token_falso)
        assert result is None

    def test_contiene_campo_exp(self):
        """El token decodificado debe contener el campo de expiración."""
        token = create_access_token({"sub": "user1"})
        payload = decode_token(token)
        assert "exp" in payload

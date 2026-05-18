"""
PRUEBAS UNITARIAS — Módulo de recuperación híbrida
Cubre: detect_areas_from_query (no requiere Neo4j ni LanceDB)
"""

import pytest
from data_engineering.retrieval.hybrid_retriever import detect_areas_from_query


class TestDetectAreasFromQuery:
    """Tests para la detección automática de áreas legales."""

    # ── Casos directos ─────────────────────────────────────────────
    def test_detecta_area_laboral(self):
        result = detect_areas_from_query("Me despidieron sin causa justificada")
        assert "laboral" in result

    def test_detecta_area_penal(self):
        result = detect_areas_from_query("Me robaron el celular en la calle")
        assert "penal" in result

    def test_detecta_area_transito(self):
        result = detect_areas_from_query("Tuve un accidente de tránsito con otro vehículo")
        assert "tránsito" in result

    def test_detecta_area_civil(self):
        result = detect_areas_from_query("Mi arrendatario no paga el alquiler del contrato")
        assert "civil" in result

    def test_detecta_area_tributario(self):
        result = detect_areas_from_query("Tengo una multa del SIN por impuesto IVA")
        assert "tributario" in result

    def test_detecta_area_familiar(self):
        result = detect_areas_from_query("Quiero el divorcio y la tuición de mi hijo")
        assert "familiar" in result

    def test_detecta_area_comercial(self):
        result = detect_areas_from_query("Mi empresa entró en quiebra")
        assert "comercial" in result

    # ── Casos compuestos ────────────────────────────────────────────
    def test_detecta_multiples_areas(self):
        """Un accidente con trabajador en horario laboral puede ser tránsito + laboral."""
        result = detect_areas_from_query(
            "Tuve un accidente mientras trabajaba y el empleador no quiere pagar"
        )
        assert len(result) >= 2

    # ── Caso por defecto ────────────────────────────────────────────
    def test_retorna_civil_por_defecto_si_no_detecta_nada(self):
        """Si no hay palabras clave, debe retornar ['civil'] como fallback."""
        result = detect_areas_from_query("necesito ayuda con algo")
        assert result == ["civil"]

    # ── Robustez ────────────────────────────────────────────────────
    def test_es_case_insensitive(self):
        """La detección no debe distinguir mayúsculas."""
        result_lower = detect_areas_from_query("me robaron")
        result_upper = detect_areas_from_query("ME ROBARON")
        assert result_lower == result_upper

    def test_maneja_cadena_vacia(self):
        """Una cadena vacía debe retornar el área por defecto."""
        result = detect_areas_from_query("")
        assert result == ["civil"]

    def test_retorna_lista(self):
        """Siempre debe retornar una lista, nunca None."""
        result = detect_areas_from_query("cualquier texto")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_no_duplica_areas(self):
        """Si una palabra aparece dos veces, el área no se debe duplicar."""
        result = detect_areas_from_query("despido despido despido")
        assert result.count("laboral") == 1

"""
Endpoints de abogados:
- GET /lawyers            → lista abogados (con filtros opcionales)
- GET /lawyers/{area}     → abogados por área legal
"""

from fastapi import APIRouter, Query
from data_engineering.graph.neo4j_builder import get_lawyers_for_areas


router = APIRouter(prefix="/lawyers", tags=["lawyers"])


@router.get("")
def get_lawyers(
    areas: str = Query(default="", description="Áreas separadas por coma: penal,civil"),
    ciudad: str = Query(default=None, description="Ciudad: La Paz, Santa Cruz, Cochabamba"),
):
    """Obtiene abogados filtrados por área legal y/o ciudad."""
    area_list = [a.strip() for a in areas.split(",") if a.strip()] if areas else []

    if not area_list:
        area_list = ["penal", "civil", "laboral", "tránsito", "familiar"]

    lawyers = get_lawyers_for_areas(area_list, ciudad=ciudad)
    return {"lawyers": lawyers, "total": len(lawyers)}


@router.get("/{area}")
def get_lawyers_by_area(area: str, ciudad: str = Query(default=None)):
    """Obtiene abogados especializados en un área legal específica."""
    lawyers = get_lawyers_for_areas([area], ciudad=ciudad)
    return {"area": area, "lawyers": lawyers, "total": len(lawyers)}

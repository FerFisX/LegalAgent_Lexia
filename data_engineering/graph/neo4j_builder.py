"""
Constructor del grafo legal en Neo4j.

Crea nodos y relaciones que permiten el Graph RAG:
- Un caso puede cruzar múltiples áreas legales
- Se trazan relaciones entre artículos (deroga, modifica, complementa)
- Se vinculan artículos con procesos, documentos y abogados
"""

import os
from contextlib import contextmanager

from loguru import logger
from neo4j import GraphDatabase, Session

from data_engineering.parsing.law_parser import ParsedLaw, LegalArticle


# ── Conexión ──────────────────────────────────────────────────────────────────

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "lexia_neo4j_pass")


def _get_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )


@contextmanager
def _session():
    driver = _get_driver()
    with driver.session() as session:
        yield session
    driver.close()


# ── Inicialización del esquema ────────────────────────────────────────────────

SCHEMA_QUERIES = [
    # Constraints (unicidad)
    "CREATE CONSTRAINT area_nombre IF NOT EXISTS FOR (a:AreaLegal) REQUIRE a.nombre IS UNIQUE",
    "CREATE CONSTRAINT ley_id IF NOT EXISTS FOR (l:Ley) REQUIRE l.doc_id IS UNIQUE",
    "CREATE CONSTRAINT articulo_id IF NOT EXISTS FOR (a:Articulo) REQUIRE a.articulo_id IS UNIQUE",
    "CREATE CONSTRAINT proceso_nombre IF NOT EXISTS FOR (p:Proceso) REQUIRE p.nombre IS UNIQUE",
    "CREATE CONSTRAINT abogado_id IF NOT EXISTS FOR (ab:Abogado) REQUIRE ab.abogado_id IS UNIQUE",
    # Índices para búsqueda rápida
    "CREATE INDEX articulo_numero IF NOT EXISTS FOR (a:Articulo) ON (a.numero)",
    "CREATE INDEX ley_numero IF NOT EXISTS FOR (l:Ley) ON (l.numero)",
    "CREATE INDEX ley_tipo IF NOT EXISTS FOR (l:Ley) ON (l.tipo)",
]


def init_schema() -> None:
    """Crea constraints e índices en Neo4j."""
    with _session() as session:
        for query in SCHEMA_QUERIES:
            try:
                session.run(query)
            except Exception as e:
                logger.warning(f"Schema query falló (puede que ya exista): {e}")
    logger.success("Esquema Neo4j inicializado.")


# ── Datos base: Áreas Legales y Procesos ──────────────────────────────────────

AREAS_LEGALES = [
    {"nombre": "penal", "descripcion": "Derecho Penal - delitos, sanciones, proceso penal"},
    {"nombre": "civil", "descripcion": "Derecho Civil - contratos, propiedad, familia"},
    {"nombre": "laboral", "descripcion": "Derecho Laboral - trabajo, empleadores, trabajadores"},
    {"nombre": "tránsito", "descripcion": "Derecho de Tránsito - vehículos, accidentes viales"},
    {"nombre": "comercial", "descripcion": "Derecho Comercial - empresas, sociedades, mercantil"},
    {"nombre": "administrativo", "descripcion": "Derecho Administrativo - estado, gobierno"},
    {"nombre": "constitucional", "descripcion": "Derecho Constitucional - derechos, garantías"},
    {"nombre": "tributario", "descripcion": "Derecho Tributario - impuestos, aduana"},
    {"nombre": "familiar", "descripcion": "Derecho de Familia - matrimonio, divorcio, tuición"},
]

PROCESOS_BASE = [
    {
        "nombre": "Denuncia Penal",
        "institucion": "Fiscalía General del Estado",
        "descripcion": "Presentar denuncia ante el Ministerio Público",
        "pasos": "1. Ir a la Fiscalía más cercana | 2. Llevar documentos de identidad | 3. Describir los hechos ante el fiscal | 4. Firmar la denuncia",
        "area": "penal",
        "documentos_requeridos": "Carnet de identidad, Pruebas o evidencias disponibles",
    },
    {
        "nombre": "Demanda Laboral",
        "institucion": "Ministerio de Trabajo, Empleo y Previsión Social",
        "descripcion": "Reclamar derechos laborales vulnerados",
        "pasos": "1. Ir al Ministerio de Trabajo | 2. Llenar formulario de conciliación | 3. Asistir a audiencia | 4. Si no hay acuerdo, demandar ante juzgado laboral",
        "area": "laboral",
        "documentos_requeridos": "Contrato de trabajo, Recibos de pago, Carnet de identidad",
    },
    {
        "nombre": "Denuncia por Accidente de Tránsito",
        "institucion": "Policía Boliviana - DIPROVE / Tránsito",
        "descripcion": "Reportar accidente de tránsito con daños o lesiones",
        "pasos": "1. Llamar al 110 (Policía) | 2. No mover los vehículos | 3. Obtener informe policial | 4. Acudir al médico forense si hay lesiones | 5. Denunciar en Fiscalía si hay delito",
        "area": "tránsito",
        "documentos_requeridos": "Carnet de identidad, SOAT del vehículo, Informe policial",
    },
    {
        "nombre": "Demanda Civil",
        "institucion": "Juzgado Civil",
        "descripcion": "Reclamar derechos civiles (contratos, propiedad, daños)",
        "pasos": "1. Contratar abogado | 2. Presentar demanda en juzgado civil | 3. Notificación al demandado | 4. Audiencia | 5. Sentencia",
        "area": "civil",
        "documentos_requeridos": "Carnet de identidad, Pruebas del derecho reclamado, Patrocinio legal",
    },
    {
        "nombre": "Recurso Tributario",
        "institucion": "Servicio de Impuestos Nacionales (SIN)",
        "descripcion": "Impugnar resoluciones tributarias",
        "pasos": "1. Presentar Recurso de Alzada ante AISEM | 2. Si no procede, Recurso Jerárquico | 3. Proceso contencioso-administrativo",
        "area": "tributario",
        "documentos_requeridos": "Resolución impugnada, Carnet de identidad, NIT",
    },
]

# Base de datos simulada de abogados
ABOGADOS_BASE = [
    {
        "abogado_id": "ab_001",
        "nombre": "Dr. Carlos Mendoza Quispe",
        "especialidades": ["penal", "tránsito"],
        "ciudad": "La Paz",
        "telefono": "+591 2 234-5678",
        "email": "c.mendoza@lexbolivia.bo",
        "matricula": "CAAP-2341",
        "experiencia_años": 12,
    },
    {
        "abogado_id": "ab_002",
        "nombre": "Dra. María Fernández Rojas",
        "especialidades": ["laboral", "civil"],
        "ciudad": "Santa Cruz",
        "telefono": "+591 3 345-6789",
        "email": "m.fernandez@lexbolivia.bo",
        "matricula": "CASC-1872",
        "experiencia_años": 8,
    },
    {
        "abogado_id": "ab_003",
        "nombre": "Dr. Jorge Mamani Condori",
        "especialidades": ["civil", "familiar", "comercial"],
        "ciudad": "Cochabamba",
        "telefono": "+591 4 456-7890",
        "email": "j.mamani@lexbolivia.bo",
        "matricula": "CACB-3201",
        "experiencia_años": 15,
    },
    {
        "abogado_id": "ab_004",
        "nombre": "Dra. Ana Gutierrez Vidal",
        "especialidades": ["tributario", "administrativo", "comercial"],
        "ciudad": "La Paz",
        "telefono": "+591 2 567-8901",
        "email": "a.gutierrez@lexbolivia.bo",
        "matricula": "CAAP-4512",
        "experiencia_años": 10,
    },
    {
        "abogado_id": "ab_005",
        "nombre": "Dr. Roberto Alarcón Paz",
        "especialidades": ["penal"],
        "ciudad": "Santa Cruz",
        "telefono": "+591 3 678-9012",
        "email": "r.alarcon@lexbolivia.bo",
        "matricula": "CASC-2198",
        "experiencia_años": 18,
    },
    {
        "abogado_id": "ab_006",
        "nombre": "Dra. Patricia Salinas Torrez",
        "especialidades": ["familiar", "civil"],
        "ciudad": "Cochabamba",
        "telefono": "+591 4 789-0123",
        "email": "p.salinas@lexbolivia.bo",
        "matricula": "CACB-1654",
        "experiencia_años": 7,
    },
]


# ── Inserción de nodos ────────────────────────────────────────────────────────

def _seed_areas(session: Session) -> None:
    """Crea nodos de áreas legales base."""
    for area in AREAS_LEGALES:
        session.run(
            """
            MERGE (a:AreaLegal {nombre: $nombre})
            SET a.descripcion = $descripcion
            """,
            nombre=area["nombre"],
            descripcion=area["descripcion"],
        )
    logger.debug(f"Áreas legales insertadas: {len(AREAS_LEGALES)}")


def _seed_processes(session: Session) -> None:
    """Crea nodos de procesos legales y los vincula a áreas."""
    for proc in PROCESOS_BASE:
        session.run(
            """
            MERGE (p:Proceso {nombre: $nombre})
            SET p.institucion = $institucion,
                p.descripcion = $descripcion,
                p.pasos = $pasos,
                p.documentos_requeridos = $docs
            WITH p
            MATCH (a:AreaLegal {nombre: $area})
            MERGE (p)-[:PERTENECE_A]->(a)
            """,
            nombre=proc["nombre"],
            institucion=proc["institucion"],
            descripcion=proc["descripcion"],
            pasos=proc["pasos"],
            docs=proc["documentos_requeridos"],
            area=proc["area"],
        )
    logger.debug(f"Procesos insertados: {len(PROCESOS_BASE)}")


def _seed_lawyers(session: Session) -> None:
    """Crea nodos de abogados y los vincula a sus especialidades."""
    for ab in ABOGADOS_BASE:
        session.run(
            """
            MERGE (ab:Abogado {abogado_id: $abogado_id})
            SET ab.nombre = $nombre,
                ab.ciudad = $ciudad,
                ab.telefono = $telefono,
                ab.email = $email,
                ab.matricula = $matricula,
                ab.experiencia_años = $exp
            """,
            abogado_id=ab["abogado_id"],
            nombre=ab["nombre"],
            ciudad=ab["ciudad"],
            telefono=ab["telefono"],
            email=ab["email"],
            matricula=ab["matricula"],
            exp=ab["experiencia_años"],
        )
        for especialidad in ab["especialidades"]:
            session.run(
                """
                MATCH (ab:Abogado {abogado_id: $abogado_id})
                MATCH (a:AreaLegal {nombre: $area})
                MERGE (ab)-[:ESPECIALISTA_EN]->(a)
                """,
                abogado_id=ab["abogado_id"],
                area=especialidad,
            )
    logger.debug(f"Abogados insertados: {len(ABOGADOS_BASE)}")


def upsert_law(law: ParsedLaw, session: Session) -> None:
    """Inserta o actualiza un nodo Ley y sus artículos en el grafo."""

    # Nodo Ley
    session.run(
        """
        MERGE (l:Ley {doc_id: $doc_id})
        SET l.tipo = $tipo,
            l.numero = $numero,
            l.titulo = $titulo,
            l.fecha_publicacion = $fecha,
            l.total_articulos = $total
        """,
        doc_id=law.doc_id,
        tipo=law.tipo,
        numero=law.numero,
        titulo=law.titulo,
        fecha=law.fecha_publicacion,
        total=law.total_articles,
    )

    # Vincular Ley → AreaLegal
    for area in law.areas:
        session.run(
            """
            MATCH (l:Ley {doc_id: $doc_id})
            MATCH (a:AreaLegal {nombre: $area})
            MERGE (l)-[:PERTENECE_A]->(a)
            """,
            doc_id=law.doc_id,
            area=area,
        )

    # Nodos Artículo
    for article in law.articles:
        articulo_id = f"{law.doc_id}_art_{article.article_number}"

        session.run(
            """
            MERGE (art:Articulo {articulo_id: $articulo_id})
            SET art.numero = $numero,
                art.texto = $texto,
                art.capitulo = $capitulo,
                art.titulo_seccion = $titulo_seccion,
                art.es_derogado = $derogado,
                art.doc_id = $doc_id
            WITH art
            MATCH (l:Ley {doc_id: $doc_id})
            MERGE (l)-[:CONTIENE]->(art)
            """,
            articulo_id=articulo_id,
            numero=article.article_number,
            texto=article.text[:500],  # resumen en nodo, texto completo en ChromaDB
            capitulo=article.chapter,
            titulo_seccion=article.title_section,
            derogado=article.is_derogated,
            doc_id=law.doc_id,
        )

        # Relación DEROGA entre artículos
        for derogated_num in article.derogates:
            target_id = f"{law.doc_id}_art_{derogated_num}"
            session.run(
                """
                MATCH (art:Articulo {articulo_id: $source_id})
                MERGE (target:Articulo {articulo_id: $target_id})
                ON CREATE SET target.numero = $num, target.doc_id = $doc_id
                MERGE (art)-[:DEROGA]->(target)
                """,
                source_id=articulo_id,
                target_id=target_id,
                num=derogated_num,
                doc_id=law.doc_id,
            )

        # Relación MODIFICA entre artículos
        for modified_num in article.modifies:
            target_id = f"{law.doc_id}_art_{modified_num}"
            session.run(
                """
                MATCH (art:Articulo {articulo_id: $source_id})
                MERGE (target:Articulo {articulo_id: $target_id})
                ON CREATE SET target.numero = $num, target.doc_id = $doc_id
                MERGE (art)-[:MODIFICA]->(target)
                """,
                source_id=articulo_id,
                target_id=target_id,
                num=modified_num,
                doc_id=law.doc_id,
            )

        # Relación REFERENCIA entre artículos (referencias cruzadas)
        for ref_num in article.cross_references:
            ref_id = f"{law.doc_id}_art_{ref_num}"
            session.run(
                """
                MATCH (art:Articulo {articulo_id: $source_id})
                MERGE (ref:Articulo {articulo_id: $ref_id})
                ON CREATE SET ref.numero = $num, ref.doc_id = $doc_id
                MERGE (art)-[:REFERENCIA]->(ref)
                """,
                source_id=articulo_id,
                ref_id=ref_id,
                num=ref_num,
                doc_id=law.doc_id,
            )

        # Vincular artículos a procesos por área
        for area in law.areas:
            session.run(
                """
                MATCH (art:Articulo {articulo_id: $articulo_id})
                MATCH (p:Proceso)-[:PERTENECE_A]->(a:AreaLegal {nombre: $area})
                MERGE (art)-[:APLICA_EN]->(p)
                """,
                articulo_id=articulo_id,
                area=area,
            )

    logger.debug(f"Grafo actualizado: {law.doc_id} ({law.total_articles} artículos)")


# ── Queries de Graph RAG ──────────────────────────────────────────────────────

def expand_context(
    chunk_ids: list[str],
    hops: int = 2,
) -> list[dict]:
    """
    Dado un conjunto de chunk_ids encontrados por ChromaDB,
    expande el contexto usando el grafo (relaciones entre artículos).

    Args:
        chunk_ids: IDs de chunks encontrados por búsqueda semántica.
        hops: Profundidad de expansión en el grafo.

    Returns:
        Lista de artículos relacionados con su texto y metadata.
    """
    # Extraer doc_id y número de artículo de cada chunk_id
    # Formato: "{doc_id}_art_{num}_chunk_{i}"
    articulo_ids = set()
    for chunk_id in chunk_ids:
        parts = chunk_id.split("_art_")
        if len(parts) == 2:
            doc_id = parts[0]
            art_num_part = parts[1].split("_chunk_")[0]
            articulo_ids.add(f"{doc_id}_art_{art_num_part}")

    if not articulo_ids:
        return []

    with _session() as session:
        result = session.run(
            f"""
            MATCH (art:Articulo)
            WHERE art.articulo_id IN $articulo_ids
            // Expandir {hops} hops: relaciones entre artículos
            CALL apoc.path.subgraphNodes(art, {{
                relationshipFilter: "DEROGA|MODIFICA|REFERENCIA|COMPLEMENTA",
                maxLevel: {hops},
                labelFilter: "Articulo"
            }}) YIELD node AS related
            WHERE NOT related.es_derogado
            RETURN DISTINCT
                related.articulo_id AS articulo_id,
                related.numero AS numero,
                related.texto AS texto,
                related.capitulo AS capitulo,
                related.doc_id AS doc_id
            LIMIT 20
            """,
            articulo_ids=list(articulo_ids),
        )

        expanded = [dict(record) for record in result]

    logger.debug(f"Graph RAG expandió {len(chunk_ids)} chunks → {len(expanded)} artículos")
    return expanded


def get_processes_for_areas(areas: list[str]) -> list[dict]:
    """
    Obtiene los procesos legales recomendados para un conjunto de áreas.
    """
    with _session() as session:
        result = session.run(
            """
            MATCH (p:Proceso)-[:PERTENECE_A]->(a:AreaLegal)
            WHERE a.nombre IN $areas
            RETURN DISTINCT
                p.nombre AS nombre,
                p.institucion AS institucion,
                p.descripcion AS descripcion,
                p.pasos AS pasos,
                p.documentos_requeridos AS documentos,
                a.nombre AS area
            """,
            areas=areas,
        )
        return [dict(r) for r in result]


def get_lawyers_for_areas(areas: list[str], ciudad: str = None) -> list[dict]:
    """
    Obtiene abogados especializados en las áreas detectadas en el caso.
    """
    with _session() as session:
        city_filter = "AND ab.ciudad = $ciudad" if ciudad else ""
        result = session.run(
            f"""
            MATCH (ab:Abogado)-[:ESPECIALISTA_EN]->(a:AreaLegal)
            WHERE a.nombre IN $areas {city_filter}
            RETURN DISTINCT
                ab.nombre AS nombre,
                ab.ciudad AS ciudad,
                ab.telefono AS telefono,
                ab.email AS email,
                ab.matricula AS matricula,
                ab.experiencia_años AS experiencia,
                collect(a.nombre) AS especialidades
            ORDER BY ab.experiencia_años DESC
            LIMIT 5
            """,
            areas=areas,
            ciudad=ciudad,
        )
        return [dict(r) for r in result]


# ── Setup inicial ─────────────────────────────────────────────────────────────

def seed_base_data() -> None:
    """Inserta datos base: áreas, procesos y abogados simulados."""
    with _session() as session:
        _seed_areas(session)
        _seed_processes(session)
        _seed_lawyers(session)
    logger.success("Datos base insertados en Neo4j.")


def build_graph_from_laws(laws: list[ParsedLaw]) -> None:
    """Construye el grafo completo desde una lista de leyes parseadas."""
    with _session() as session:
        for law in laws:
            try:
                upsert_law(law, session)
            except Exception as e:
                logger.error(f"Error insertando {law.doc_id} en Neo4j: {e}")

    logger.success(f"Grafo construido: {len(laws)} leyes procesadas.")

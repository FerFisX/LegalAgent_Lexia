"""
Script de exploración del grafo Neo4j de Lexia.
Corre con: python ver_neo4j.py
"""

from neo4j import GraphDatabase

# ── Conexión ──────────────────────────────────────────────────────────────────
URI      = "bolt://localhost:7687"
USER     = "neo4j"
PASSWORD = "lexia_neo4j_pass"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def run(query, **params):
    with driver.session() as session:
        return [dict(r) for r in session.run(query, **params)]

def titulo(texto):
    print("\n" + "═" * 60)
    print(f"  {texto}")
    print("═" * 60)

# ══════════════════════════════════════════════════════════════
# 1. RESUMEN GENERAL DEL GRAFO
# ══════════════════════════════════════════════════════════════
titulo("1. RESUMEN GENERAL DEL GRAFO")

conteos = run("""
    MATCH (n)
    RETURN labels(n)[0] AS tipo, count(n) AS cantidad
    ORDER BY cantidad DESC
""")
for r in conteos:
    print(f"  {r['tipo']:<20} → {r['cantidad']} nodos")

relaciones = run("""
    MATCH ()-[r]->()
    RETURN type(r) AS relacion, count(r) AS cantidad
    ORDER BY cantidad DESC
""")
print()
for r in relaciones:
    print(f"  [{r['relacion']}]  →  {r['cantidad']} relaciones")


# ══════════════════════════════════════════════════════════════
# 2. ÁREAS LEGALES
# ══════════════════════════════════════════════════════════════
titulo("2. ÁREAS LEGALES")

areas = run("MATCH (a:AreaLegal) RETURN a.nombre AS nombre, a.descripcion AS descripcion ORDER BY a.nombre")
for a in areas:
    print(f"  • {a['nombre']:<20} — {a['descripcion']}")


# ══════════════════════════════════════════════════════════════
# 3. PROCESOS LEGALES
# ══════════════════════════════════════════════════════════════
titulo("3. PROCESOS LEGALES")

procesos = run("""
    MATCH (p:Proceso)-[:PERTENECE_A]->(a:AreaLegal)
    RETURN p.nombre AS nombre, p.institucion AS institucion, a.nombre AS area
    ORDER BY a.nombre
""")
for p in procesos:
    print(f"  [{p['area']:<15}] {p['nombre']}")
    print(f"                    → {p['institucion']}")


# ══════════════════════════════════════════════════════════════
# 4. ABOGADOS Y SUS ESPECIALIDADES
# ══════════════════════════════════════════════════════════════
titulo("4. ABOGADOS REGISTRADOS")

abogados = run("""
    MATCH (ab:Abogado)-[:ESPECIALISTA_EN]->(a:AreaLegal)
    RETURN ab.nombre AS nombre, ab.ciudad AS ciudad,
           ab.experiencia_años AS exp, ab.matricula AS matricula,
           collect(a.nombre) AS especialidades
    ORDER BY ab.ciudad, ab.experiencia_años DESC
""")
for ab in abogados:
    esp = ", ".join(ab['especialidades'])
    print(f"  {ab['nombre']}")
    print(f"    Ciudad: {ab['ciudad']} | Exp: {ab['exp']} años | Matrícula: {ab['matricula']}")
    print(f"    Especialidades: {esp}")
    print()


# ══════════════════════════════════════════════════════════════
# 5. LEYES CARGADAS EN EL GRAFO
# ══════════════════════════════════════════════════════════════
titulo("5. LEYES EN EL GRAFO")

leyes = run("""
    MATCH (l:Ley)
    OPTIONAL MATCH (l)-[:PERTENECE_A]->(a:AreaLegal)
    RETURN l.doc_id AS id, l.tipo AS tipo, l.numero AS numero,
           l.titulo AS titulo, l.total_articulos AS articulos,
           collect(a.nombre) AS areas
    ORDER BY l.tipo, l.numero
""")
if not leyes:
    print("  ⚠  No hay leyes cargadas aún.")
    print("     Ejecuta el pipeline ETL para cargar documentos legales.")
else:
    for l in leyes:
        areas_str = ", ".join(l['areas']) if l['areas'] else "—"
        print(f"  [{l['tipo']}] Nº {l['numero']} — {l['titulo'][:60]}")
        print(f"    Artículos: {l['articulos']} | Áreas: {areas_str}")
        print()


# ══════════════════════════════════════════════════════════════
# 6. ARTÍCULOS (primeros 10 si hay leyes cargadas)
# ══════════════════════════════════════════════════════════════
titulo("6. MUESTRA DE ARTÍCULOS (primeros 10)")

articulos = run("""
    MATCH (art:Articulo)<-[:CONTIENE]-(l:Ley)
    RETURN art.articulo_id AS id, art.numero AS numero,
           l.titulo AS ley, art.capitulo AS capitulo,
           left(art.texto, 120) AS texto_resumen
    ORDER BY art.articulo_id
    LIMIT 10
""")
if not articulos:
    print("  ⚠  No hay artículos cargados aún.")
else:
    for art in articulos:
        print(f"  Art. {art['numero']} — {art['ley'][:50]}")
        print(f"    Capítulo: {art['capitulo']}")
        print(f"    {art['texto_resumen']}...")
        print()


# ══════════════════════════════════════════════════════════════
# 7. RELACIONES ENTRE ARTÍCULOS
# ══════════════════════════════════════════════════════════════
titulo("7. RELACIONES ENTRE ARTÍCULOS (DEROGA / MODIFICA / REFERENCIA)")

rels = run("""
    MATCH (a1:Articulo)-[r:DEROGA|MODIFICA|REFERENCIA]->(a2:Articulo)
    RETURN type(r) AS tipo, a1.articulo_id AS origen, a2.articulo_id AS destino
    LIMIT 20
""")
if not rels:
    print("  (Sin relaciones entre artículos aún — se crean al cargar leyes)")
else:
    for r in rels:
        print(f"  {r['origen']}  --[{r['tipo']}]-->  {r['destino']}")


# ══════════════════════════════════════════════════════════════
# 8. CONSULTA LIBRE — Abogados de penal en La Paz
# ══════════════════════════════════════════════════════════════
titulo("8. EJEMPLO: Abogados de PENAL en La Paz")

ejemplo = run("""
    MATCH (ab:Abogado)-[:ESPECIALISTA_EN]->(a:AreaLegal {nombre: 'penal'})
    WHERE ab.ciudad = 'La Paz'
    RETURN ab.nombre AS nombre, ab.telefono AS telefono, ab.experiencia_años AS exp
    ORDER BY exp DESC
""")
if not ejemplo:
    print("  (Sin resultados)")
else:
    for ab in ejemplo:
        print(f"  {ab['nombre']} — Tel: {ab['telefono']} ({ab['exp']} años)")


# ══════════════════════════════════════════════════════════════
# 9. CONSULTA LIBRE — Procesos para área laboral
# ══════════════════════════════════════════════════════════════
titulo("9. EJEMPLO: Proceso para caso LABORAL")

proc_ej = run("""
    MATCH (p:Proceso)-[:PERTENECE_A]->(a:AreaLegal {nombre: 'laboral'})
    RETURN p.nombre AS nombre, p.institucion AS institucion, p.pasos AS pasos
""")
for p in proc_ej:
    print(f"  Proceso: {p['nombre']}")
    print(f"  Institución: {p['institucion']}")
    print(f"  Pasos: {p['pasos']}")
    print()


driver.close()
print("\n✅ Exploración completa. Cierre de conexión con Neo4j.\n")

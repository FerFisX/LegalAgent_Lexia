"""
Configuración de la base de datos PostgreSQL con SQLAlchemy.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.core.config import settings


# Usamos pg8000 (Python puro) en lugar de psycopg2 para evitar
# problemas de encoding con libpq en Windows con locale en espanol.
_db_url = (
    f"postgresql+pg8000://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@127.0.0.1:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

import sys
print(f"[DB] Conectando a: {_db_url}", file=sys.stderr)

engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency de FastAPI para obtener sesión de DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

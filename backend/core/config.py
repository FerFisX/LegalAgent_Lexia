"""
Configuración central del backend.
Lee todas las variables del .env con validación de tipos via Pydantic.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────
    APP_NAME: str = "LegalAgent Lexia"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = Field(default="lexia-secret-key-change-in-production")

    # ── JWT ───────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7   # 7 días

    # ── PostgreSQL ────────────────────────────────────────────────
    POSTGRES_USER: str = "lexia_user"
    POSTGRES_PASSWORD: str = "lexia_pass"
    POSTGRES_DB: str = "lexia_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Neo4j ─────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "lexia_neo4j_pass"

    # ── LLM ───────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ── Embeddings ────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DEVICE: str = "cpu"

    # ── Rate limiting invitado ────────────────────────────────────
    GUEST_MAX_QUERIES: int = 3

    # ── LanceDB ───────────────────────────────────────────────────
    CHROMA_COLLECTION: str = "lexia_legal_docs"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

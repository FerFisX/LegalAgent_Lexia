"""
Punto de entrada del backend — FastAPI.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.core.config import settings
from backend.core.database import engine, Base
from backend.models import User, Conversation, Message  # noqa: F401 — registra los modelos en Base.metadata
from backend.api.routes import auth, chat, lawyers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup y shutdown de la aplicación."""
    # Crear tablas en PostgreSQL al arrancar
    logger.info("Creando tablas en PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    logger.success("Base de datos lista.")
    yield
    logger.info("Apagando servidor...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agente legal conversacional para Bolivia — Legislación boliviana con Graph RAG",
    lifespan=lifespan,
)

# ── CORS (para el frontend Next.js) ──────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(lawyers.router)


@app.get("/", tags=["health"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

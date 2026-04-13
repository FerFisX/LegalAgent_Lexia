"""
Endpoints de autenticación:
- POST /auth/signup     → registro
- POST /auth/login      → login
- POST /auth/guest      → sesión de invitado
- GET  /auth/me         → perfil del usuario actual
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import hash_password, verify_password, create_access_token
from backend.core.config import settings
from backend.models.user import User
from backend.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserResponse
from backend.api.middleware.auth_middleware import get_current_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """Registro de nuevo usuario."""
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado",
        )

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        is_guest=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        is_guest=False,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Login con email y contraseña."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        is_guest=False,
    )


@router.post("/guest", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def create_guest(db: Session = Depends(get_db)):
    """
    Crea una sesión de invitado con límite de consultas.
    No requiere email ni contraseña.
    """
    guest = User(
        id=str(uuid.uuid4()),
        is_guest=True,
        guest_query_count=0,
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)

    token = create_access_token({"sub": guest.id, "is_guest": True})
    return TokenResponse(
        access_token=token,
        user_id=guest.id,
        is_guest=True,
        guest_queries_remaining=settings.GUEST_MAX_QUERIES,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Perfil del usuario autenticado."""
    return current_user

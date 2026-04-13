from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    username: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_guest: bool = False
    user_id: str
    username: str | None = None
    guest_queries_remaining: int | None = None


class UserResponse(BaseModel):
    id: str
    email: str | None
    username: str | None
    is_guest: bool
    guest_query_count: int

    class Config:
        from_attributes = True

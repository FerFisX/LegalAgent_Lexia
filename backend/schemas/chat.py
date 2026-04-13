from pydantic import BaseModel
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None   # None = nueva conversación


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    agent_metadata: dict | None = None

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageResponse
    detected_areas: list[str] = []
    complexity: str | None = None
    suggested_lawyers: list[dict] = []
    suggested_processes: list[dict] = []


class ConversationResponse(BaseModel):
    id: str
    title: str
    status: str
    complexity: str | None
    detected_areas: list | None
    created_at: datetime
    messages: list[MessageResponse] = []

    class Config:
        from_attributes = True

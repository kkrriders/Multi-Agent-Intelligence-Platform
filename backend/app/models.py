from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str


class ProjectOut(BaseModel):
    id: str
    name: str
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str = "New conversation"


class ConversationOut(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: datetime


class MemorySearchResult(BaseModel):
    score: float
    project_id: str
    conversation_id: str
    run_id: str
    input: str
    output: str


class RunCreate(BaseModel):
    input: str


class RunEventOut(BaseModel):
    id: str
    step_name: str
    payload: dict
    created_at: datetime


class Citation(BaseModel):
    index: int
    document_id: str
    filename: str
    content: str


class RunOut(BaseModel):
    id: str
    status: str
    output: str | None
    events: list[RunEventOut]
    citations: list[Citation] = []


class ToolCreate(BaseModel):
    name: str
    type: str
    config: dict
    permissions: dict = {}


class ToolOut(BaseModel):
    id: str
    name: str
    type: str
    config: dict
    permissions: dict
    created_at: datetime


class ToolInvokeResult(BaseModel):
    status: int
    body: str


class DocumentOut(BaseModel):
    id: str
    project_id: str
    filename: str
    mime_type: str
    storage_path: str
    status: str
    error: str | None = None
    created_at: datetime

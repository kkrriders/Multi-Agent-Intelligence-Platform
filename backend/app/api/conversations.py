from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import get_user_client
from app.models import ConversationCreate, ConversationOut

router = APIRouter(tags=["conversations"])


@router.post("/projects/{project_id}/conversations", response_model=ConversationOut)
def create_conversation(project_id: str, body: ConversationCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = client.table("conversations").insert(
        {"project_id": project_id, "title": body.title}
    ).execute()
    return result.data[0]


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationOut])
def list_conversations(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = (
        client.table("conversations")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data

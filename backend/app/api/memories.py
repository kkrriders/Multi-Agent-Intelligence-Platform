from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import fetch_maybe_one, get_user_client
from app.memory import search_memory
from app.models import MemorySearchResult

router = APIRouter(tags=["memories"])


@router.get("/projects/{project_id}/memories/search", response_model=list[MemorySearchResult])
def search_project_memory(project_id: str, q: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    project = fetch_maybe_one(client.table("projects").select("id").eq("id", project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return search_memory(project_id, q)

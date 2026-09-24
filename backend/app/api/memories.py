from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, text

from app.db import get_db, maybe_one
from app.memory import search_memory
from app.models import MemorySearchResult

router = APIRouter(tags=["memories"])


@router.get("/projects/{project_id}/memories/search", response_model=list[MemorySearchResult])
def search_project_memory(project_id: str, q: str, conn: Connection = Depends(get_db)):
    project = maybe_one(conn.execute(text("select id from projects where id = :i"), {"i": project_id}))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return search_memory(project_id, q)

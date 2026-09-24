from fastapi import APIRouter, Depends
from sqlalchemy import Connection, text

from app.db import get_db, one, rows
from app.models import ConversationCreate, ConversationOut

router = APIRouter(tags=["conversations"])


@router.post("/projects/{project_id}/conversations", response_model=ConversationOut)
def create_conversation(project_id: str, body: ConversationCreate, conn: Connection = Depends(get_db)):
    return one(
        conn.execute(
            text("insert into conversations (project_id, title) values (:p, :t) returning *"),
            {"p": project_id, "t": body.title},
        )
    )


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationOut])
def list_conversations(project_id: str, conn: Connection = Depends(get_db)):
    return rows(
        conn.execute(
            text("select * from conversations where project_id = :p order by created_at desc"),
            {"p": project_id},
        )
    )

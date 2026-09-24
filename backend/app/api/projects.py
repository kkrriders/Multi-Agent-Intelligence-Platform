from fastapi import APIRouter, Depends
from sqlalchemy import Connection, text

from app.db import get_db, one, rows
from app.models import ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, conn: Connection = Depends(get_db)):
    return one(conn.execute(text("insert into projects (name) values (:n) returning *"), {"n": body.name}))


@router.get("", response_model=list[ProjectOut])
def list_projects(conn: Connection = Depends(get_db)):
    return rows(conn.execute(text("select * from projects order by created_at desc")))

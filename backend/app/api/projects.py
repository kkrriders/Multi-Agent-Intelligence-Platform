from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import get_user_client
from app.models import ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = client.table("projects").insert({"name": body.name}).execute()
    return result.data[0]


@router.get("", response_model=list[ProjectOut])
def list_projects(user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = client.table("projects").select("*").order("created_at", desc=True).execute()
    return result.data




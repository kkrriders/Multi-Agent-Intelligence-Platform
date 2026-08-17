import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import get_user_client
from app.models import ToolCreate, ToolInvokeResult, ToolOut
from app.tools.rest_adapter import ToolConfigError
from app.tools.rest_adapter import invoke as rest_invoke

router = APIRouter(tags=["tools"])

ADAPTERS = {"rest": rest_invoke}


@router.post("/projects/{project_id}/tools", response_model=ToolOut)
def create_tool(project_id: str, body: ToolCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = client.table("tools").insert({
        "project_id": project_id,
        "name": body.name,
        "type": body.type,
        "config": body.config,
        "permissions": body.permissions,
    }).execute()
    return result.data[0]


@router.get("/projects/{project_id}/tools", response_model=list[ToolOut])
def list_tools(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = (
        client.table("tools")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.post("/tools/{tool_id}/invoke", response_model=ToolInvokeResult)
def invoke_tool(tool_id: str, input: dict, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    tool = client.table("tools").select("*").eq("id", tool_id).maybe_single().execute().data
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    adapter = ADAPTERS.get(tool["type"])
    if adapter is None:
        raise HTTPException(status_code=400, detail=f"Unsupported tool type: {tool['type']}")

    try:
        return adapter(tool["config"], input)
    except ToolConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid tool config: missing {exc}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Tool request failed: {exc}")

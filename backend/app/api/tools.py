import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, text

from app.db import get_db, maybe_one, one, rows
from app.models import ToolCreate, ToolInvokeResult, ToolOut
from app.tools.rest_adapter import ToolConfigError
from app.tools.rest_adapter import invoke as rest_invoke

router = APIRouter(tags=["tools"])

ADAPTERS = {"rest": rest_invoke}


@router.post("/projects/{project_id}/tools", response_model=ToolOut)
def create_tool(project_id: str, body: ToolCreate, conn: Connection = Depends(get_db)):
    return one(
        conn.execute(
            text(
                "insert into tools (project_id, name, type, config, permissions) "
                "values (:p, :n, :t, cast(:c as jsonb), cast(:perm as jsonb)) returning *"
            ),
            {
                "p": project_id,
                "n": body.name,
                "t": body.type,
                "c": json.dumps(body.config),
                "perm": json.dumps(body.permissions),
            },
        )
    )


@router.get("/projects/{project_id}/tools", response_model=list[ToolOut])
def list_tools(project_id: str, conn: Connection = Depends(get_db)):
    return rows(
        conn.execute(
            text("select * from tools where project_id = :p order by created_at desc"),
            {"p": project_id},
        )
    )


@router.post("/tools/{tool_id}/invoke", response_model=ToolInvokeResult)
def invoke_tool(tool_id: str, input: dict, conn: Connection = Depends(get_db)):
    tool = maybe_one(conn.execute(text("select * from tools where id = :i"), {"i": tool_id}))
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

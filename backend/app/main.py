from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    conversations,
    documents,
    evals,
    guardrails,
    memories,
    projects,
    prompts,
    runs,
    tools,
)

app = FastAPI(title="AI Engineering Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(documents.router)
app.include_router(evals.router)
app.include_router(guardrails.router)
app.include_router(memories.router)
app.include_router(projects.router)
app.include_router(prompts.router)
app.include_router(runs.router)
app.include_router(tools.router)


@app.get("/health")
def health():
    return {"status": "ok"}

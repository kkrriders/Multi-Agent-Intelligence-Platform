from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversations, memories, projects, runs, tools

app = FastAPI(title="AI Engineering Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(memories.router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(tools.router)


@app.get("/health")
def health():
    return {"status": "ok"}

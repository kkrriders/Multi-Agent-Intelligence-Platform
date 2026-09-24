import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api import (
    alerts,
    auth_routes,
    analytics,
    conversations,
    deployments,
    documents,
    evals,
    guardrails,
    memories,
    projects,
    prompts,
    runs,
    tools,
)
from app.metrics import observe_request

app = FastAPI(title="AI Engineering Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AIRRA integration: expose per-service golden signals for Prometheus scrape.
app.mount("/metrics", make_asgi_app())


@app.middleware("http")
async def _record_api_request_metrics(request: Request, call_next):
    if request.url.path.startswith("/metrics"):
        return await call_next(request)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        observe_request("api", "500", time.perf_counter() - start)
        raise
    observe_request("api", str(response.status_code), time.perf_counter() - start)
    return response

app.include_router(alerts.router)
app.include_router(auth_routes.router)
app.include_router(analytics.router)
app.include_router(conversations.router)
app.include_router(deployments.router)
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

from datetime import datetime

from pydantic import BaseModel, model_validator


class ProjectCreate(BaseModel):
    name: str


class ProjectOut(BaseModel):
    id: str
    name: str
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str = "New conversation"


class ConversationOut(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: datetime


class MemorySearchResult(BaseModel):
    score: float
    project_id: str
    conversation_id: str
    run_id: str
    input: str
    output: str


class RunCreate(BaseModel):
    input: str | None = None
    template_id: str | None = None
    variables: dict = {}

    @model_validator(mode="after")
    def _exactly_one_source(self):
        if bool(self.input) == bool(self.template_id):
            raise ValueError("provide exactly one of 'input' or 'template_id'")
        return self


class PromptTemplateCreate(BaseModel):
    name: str
    body: str


class PromptTemplateUpdate(BaseModel):
    body: str


class PromptTemplateVersionOut(BaseModel):
    id: str
    version: int
    body: str
    variables: list[str]
    created_at: datetime


class PromptTemplateOut(BaseModel):
    id: str
    name: str
    version: int
    body: str
    variables: list[str]
    version_count: int
    created_at: datetime


class EvalItemIn(BaseModel):
    input: str
    expected: str


class EvalItemOut(BaseModel):
    id: str
    input: str
    expected: str


class EvalDatasetCreate(BaseModel):
    name: str
    items: list[EvalItemIn]


class EvalRunSummary(BaseModel):
    id: str
    dataset_id: str
    item_count: int
    accuracy: float
    hallucination_rate: float
    mean_score: float
    created_at: datetime


class EvalResultOut(BaseModel):
    id: str
    item_id: str
    output: str
    score: float
    hallucinated: bool
    reason: str


class EvalRunOut(EvalRunSummary):
    results: list[EvalResultOut] = []


class EvalDatasetOut(BaseModel):
    id: str
    name: str
    item_count: int
    latest_run: EvalRunSummary | None = None
    created_at: datetime


class EvalDatasetDetailOut(EvalDatasetOut):
    items: list[EvalItemOut] = []


class RunEventOut(BaseModel):
    id: str
    step_name: str
    payload: dict
    created_at: datetime


class Citation(BaseModel):
    index: int
    document_id: str
    filename: str
    content: str


class GuardrailEventOut(BaseModel):
    id: str
    phase: str
    kind: str
    outcome: str
    detail: dict
    created_at: datetime


class GuardrailPolicyOut(BaseModel):
    id: str | None
    kind: str
    enabled: bool
    config: dict
    created_at: datetime | None = None


class GuardrailPolicyUpdate(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


class RunLlmCallOut(BaseModel):
    node: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class RunOut(BaseModel):
    id: str
    status: str
    output: str | None
    events: list[RunEventOut]
    citations: list[Citation] = []
    guardrails: list[GuardrailEventOut] = []
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    cache_hit: bool = False
    llm_calls: list[RunLlmCallOut] = []


class AlertRuleCreate(BaseModel):
    kind: str
    threshold: float
    window_n: int = 20
    webhook_url: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.kind not in ("error_rate", "daily_spend", "p95_latency"):
            raise ValueError("kind must be one of error_rate, daily_spend, p95_latency")
        if self.threshold < 0:
            raise ValueError("threshold must be >= 0")
        if self.kind == "error_rate" and self.threshold > 1:
            raise ValueError("error_rate threshold must be <= 1")
        if self.window_n < 1:
            raise ValueError("window_n must be >= 1")
        return self


class AlertRuleUpdate(BaseModel):
    threshold: float | None = None
    window_n: int | None = None
    webhook_url: str | None = None
    enabled: bool | None = None


class AlertRuleOut(BaseModel):
    id: str
    kind: str
    threshold: float
    window_n: int
    webhook_url: str | None
    enabled: bool
    created_at: datetime


class AlertEventOut(BaseModel):
    id: str
    kind: str
    observed: float
    threshold: float
    detail: dict
    created_at: datetime


class LimitsOut(BaseModel):
    run_rate_limit_per_min: int
    deploy_api_enabled: bool = False


class DeployTargetCreate(BaseModel):
    name: str
    image_repo: str
    registry: str = "ghcr.io"
    config: dict = {}


class DeployTargetOut(BaseModel):
    id: str
    name: str
    registry: str
    image_repo: str
    config: dict
    created_at: datetime


class DeploymentCreate(BaseModel):
    target_id: str
    components: list[str] = ["backend", "frontend"]


class DeploymentOut(BaseModel):
    id: str
    target_id: str | None
    image_tag: str
    git_sha: str | None
    components: list[str]
    status: str
    log: str
    created_at: datetime


class ToolCreate(BaseModel):
    name: str
    type: str
    config: dict
    permissions: dict = {}


class ToolOut(BaseModel):
    id: str
    name: str
    type: str
    config: dict
    permissions: dict
    created_at: datetime


class ToolInvokeResult(BaseModel):
    status: int
    body: str


class DocumentOut(BaseModel):
    id: str
    project_id: str
    filename: str
    mime_type: str
    storage_path: str
    status: str
    error: str | None = None
    created_at: datetime

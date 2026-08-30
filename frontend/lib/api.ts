import { supabase } from './supabaseClient'

export type Project = { id: string; name: string; created_at: string }
export type RunEvent = { id: string; step_name: string; payload: Record<string, unknown>; created_at: string }
export type Citation = { index: number; document_id: string; filename: string; content: string }
export type GuardrailEvent = {
  id: string
  phase: string
  kind: string
  outcome: string
  detail: Record<string, unknown>
  created_at: string
}
export type GuardrailPolicy = {
  id: string | null
  kind: string
  enabled: boolean
  config: Record<string, unknown>
  created_at: string | null
}
export type RunLlmCall = {
  node: string
  model: string
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number
}
export type Run = {
  id: string
  status: string
  output: string | null
  events: RunEvent[]
  citations?: Citation[]
  guardrails?: GuardrailEvent[]
  prompt_tokens?: number | null
  completion_tokens?: number | null
  cost_usd?: number | null
  cache_hit?: boolean
  llm_calls?: RunLlmCall[]
}

export type ProjectCost = {
  totals: {
    run_count: number
    cached_run_count: number
    prompt_tokens: number
    completion_tokens: number
    cost_usd: number
    runs_missing_cost: number
    estimated_cache_savings_usd: number
  }
  by_model: {
    model: string
    calls: number
    prompt_tokens: number
    completion_tokens: number
    cost_usd: number
  }[]
  daily: { date: string; run_count: number; cost_usd: number; cached_run_count: number }[]
  recent_runs: {
    id: string
    created_at: string
    status: string
    cache_hit: boolean
    prompt_tokens: number
    completion_tokens: number
    cost_usd: number
    models: string[]
  }[]
}

const API_URL = process.env.NEXT_PUBLIC_API_URL!

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  return { Authorization: `Bearer ${data.session?.access_token}` }
}

export async function createProject(name: string): Promise<Project> {
  const res = await fetch(`${API_URL}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) throw new Error('Failed to create project')
  return res.json()
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_URL}/projects`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list projects')
  return res.json()
}

export async function createRun(
  conversationId: string,
  input: string | { template_id: string; variables: Record<string, unknown> }
): Promise<Run> {
  const body = typeof input === 'string' ? { input } : input
  const res = await fetch(`${API_URL}/conversations/${conversationId}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(60_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Failed to create run')
  }
  return res.json()
}

export type Conversation = { id: string; project_id: string; title: string; created_at: string }

export async function createConversation(projectId: string, title?: string): Promise<Conversation> {
  const res = await fetch(`${API_URL}/projects/${projectId}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(title ? { title } : {}),
  })
  if (!res.ok) throw new Error('Failed to create conversation')
  return res.json()
}

export async function listConversations(projectId: string): Promise<Conversation[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/conversations`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list conversations')
  return res.json()
}

export async function listConversationRuns(conversationId: string): Promise<Run[]> {
  const res = await fetch(`${API_URL}/conversations/${conversationId}/runs`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list conversation runs')
  return res.json()
}

export async function listProjectRuns(projectId: string): Promise<Run[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/runs`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list project runs')
  return res.json()
}

export async function getProjectCost(projectId: string): Promise<ProjectCost> {
  const res = await fetch(`${API_URL}/projects/${projectId}/cost`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load cost analytics')
  return res.json()
}

export type AlertKind = 'error_rate' | 'daily_spend' | 'p95_latency'
export type AlertRule = {
  id: string
  kind: AlertKind
  threshold: number
  window_n: number
  webhook_url: string | null
  enabled: boolean
  created_at: string
}
export type AlertEvent = {
  id: string
  kind: string
  observed: number
  threshold: number
  detail: Record<string, unknown>
  created_at: string
}

export async function getLimits(): Promise<{
  run_rate_limit_per_min: number
  deploy_api_enabled: boolean
}> {
  const res = await fetch(`${API_URL}/config/limits`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load limits')
  return res.json()
}

export type DeployTarget = {
  id: string
  name: string
  registry: string
  image_repo: string
  config: Record<string, string>
  created_at: string
}
export type Deployment = {
  id: string
  target_id: string | null
  image_tag: string
  git_sha: string | null
  components: string[]
  status: 'running' | 'succeeded' | 'failed'
  log: string
  created_at: string
}

export async function listDeployTargets(): Promise<DeployTarget[]> {
  const res = await fetch(`${API_URL}/deploy-targets`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load deploy targets')
  return res.json()
}

export async function createDeployTarget(t: {
  name: string
  image_repo: string
  registry?: string
  config?: Record<string, string>
}): Promise<DeployTarget> {
  const res = await fetch(`${API_URL}/deploy-targets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(t),
  })
  if (!res.ok) throw new Error('Failed to create deploy target')
  return res.json()
}

export async function deleteDeployTarget(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/deploy-targets/${id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error('Failed to delete deploy target')
}

export async function listDeployments(): Promise<Deployment[]> {
  const res = await fetch(`${API_URL}/deployments`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load deployments')
  return res.json()
}

export async function createDeployment(d: {
  target_id: string
  components: string[]
}): Promise<Deployment> {
  const res = await fetch(`${API_URL}/deployments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(d),
  })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Failed to start deployment')
  return res.json()
}

export async function listAlertRules(projectId: string): Promise<AlertRule[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/alert-rules`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load alert rules')
  return res.json()
}

export async function saveAlertRule(
  projectId: string,
  rule: { kind: AlertKind; threshold: number; window_n?: number; webhook_url?: string | null },
): Promise<AlertRule> {
  const res = await fetch(`${API_URL}/projects/${projectId}/alert-rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(rule),
  })
  if (!res.ok) throw new Error('Failed to save alert rule')
  return res.json()
}

export async function patchAlertRule(
  projectId: string,
  ruleId: string,
  patch: Partial<Pick<AlertRule, 'threshold' | 'window_n' | 'webhook_url' | 'enabled'>>,
): Promise<AlertRule> {
  const res = await fetch(`${API_URL}/projects/${projectId}/alert-rules/${ruleId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error('Failed to update alert rule')
  return res.json()
}

export async function deleteAlertRule(projectId: string, ruleId: string): Promise<void> {
  const res = await fetch(`${API_URL}/projects/${projectId}/alert-rules/${ruleId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error('Failed to delete alert rule')
}

export async function listAlertEvents(projectId: string): Promise<AlertEvent[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/alert-events`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load alert events')
  return res.json()
}

export type MemorySearchResult = {
  score: number
  project_id: string
  conversation_id: string
  run_id: string
  input: string
  output: string
}

export async function searchMemories(projectId: string, q: string): Promise<MemorySearchResult[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/memories/search?q=${encodeURIComponent(q)}`, {
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error('Failed to search memories')
  return res.json()
}

export type Document = {
  id: string
  project_id: string
  filename: string
  mime_type: string
  storage_path: string
  status: string
  error: string | null
  created_at: string
}

export async function uploadDocument(projectId: string, file: File): Promise<Document> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_URL}/projects/${projectId}/documents`, {
    method: 'POST',
    headers: await authHeaders(),
    body: formData,
  })
  if (!res.ok) throw new Error('Failed to upload document')
  return res.json()
}

export async function listDocuments(projectId: string): Promise<Document[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/documents`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list documents')
  return res.json()
}

export async function deleteDocument(projectId: string, documentId: string): Promise<void> {
  const res = await fetch(`${API_URL}/projects/${projectId}/documents/${documentId}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error('Failed to delete document')
}

export type Tool = {
  id: string
  name: string
  type: string
  config: Record<string, unknown>
  permissions: Record<string, unknown>
  created_at: string
}

export type ToolInvokeResult = { status: number; body: string }

export async function listTools(projectId: string): Promise<Tool[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/tools`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list tools')
  return res.json()
}

export async function createTool(
  projectId: string,
  tool: { name: string; type: string; config: Record<string, unknown> }
): Promise<Tool> {
  const res = await fetch(`${API_URL}/projects/${projectId}/tools`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(tool),
  })
  if (!res.ok) throw new Error('Failed to create tool')
  return res.json()
}

export async function invokeTool(toolId: string, input: Record<string, unknown>): Promise<ToolInvokeResult> {
  const res = await fetch(`${API_URL}/tools/${toolId}/invoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw new Error('Failed to invoke tool')
  return res.json()
}

export async function listGuardrailPolicies(projectId: string): Promise<GuardrailPolicy[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/guardrail-policies`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load guardrail policies')
  return res.json()
}

export async function putGuardrailPolicy(
  projectId: string,
  kind: string,
  update: { enabled?: boolean; config?: Record<string, unknown> }
): Promise<GuardrailPolicy> {
  const res = await fetch(`${API_URL}/projects/${projectId}/guardrail-policies/${kind}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(update),
  })
  if (!res.ok) throw new Error('Failed to save guardrail policy')
  return res.json()
}

export async function listGuardrailEvents(projectId: string): Promise<GuardrailEvent[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/guardrail-events`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load guardrail events')
  return res.json()
}

export type PromptTemplate = {
  id: string
  name: string
  version: number
  body: string
  variables: string[]
  version_count: number
  created_at: string
}
export type PromptTemplateVersion = {
  id: string
  version: number
  body: string
  variables: string[]
  created_at: string
}

export async function listPromptTemplates(projectId: string): Promise<PromptTemplate[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/prompt-templates`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load prompt templates')
  return res.json()
}

export async function createPromptTemplate(
  projectId: string,
  t: { name: string; body: string }
): Promise<PromptTemplate> {
  const res = await fetch(`${API_URL}/projects/${projectId}/prompt-templates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(t),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Failed to create template')
  }
  return res.json()
}

export async function updatePromptTemplate(
  templateId: string,
  update: { body: string }
): Promise<PromptTemplateVersion> {
  const res = await fetch(`${API_URL}/prompt-templates/${templateId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(update),
  })
  if (!res.ok) throw new Error('Failed to save template version')
  return res.json()
}

export async function listPromptTemplateVersions(templateId: string): Promise<PromptTemplateVersion[]> {
  const res = await fetch(`${API_URL}/prompt-templates/${templateId}/versions`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load versions')
  return res.json()
}

export async function runTemplateTest(
  projectId: string,
  templateId: string,
  variables: Record<string, unknown>
): Promise<Run> {
  const convs = await listConversations(projectId)
  const existing = convs.find((c) => c.title === 'Prompt tests')
  const conv = existing ?? (await createConversation(projectId, 'Prompt tests'))
  return createRun(conv.id, { template_id: templateId, variables })
}

export type EvalItem = { id: string; input: string; expected: string }
export type EvalResult = {
  id: string
  item_id: string
  output: string
  score: number
  hallucinated: boolean
  reason: string
}
export type EvalRunSummary = {
  id: string
  dataset_id: string
  item_count: number
  accuracy: number
  hallucination_rate: number
  mean_score: number
  created_at: string
}
export type EvalRun = EvalRunSummary & { results: EvalResult[] }
export type EvalDataset = {
  id: string
  name: string
  item_count: number
  latest_run: EvalRunSummary | null
  created_at: string
}
export type EvalDatasetDetail = EvalDataset & { items: EvalItem[] }

export async function listEvalDatasets(projectId: string): Promise<EvalDataset[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/eval-datasets`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load datasets')
  return res.json()
}

export async function createEvalDataset(
  projectId: string,
  ds: { name: string; items: { input: string; expected: string }[] }
): Promise<EvalDatasetDetail> {
  const res = await fetch(`${API_URL}/projects/${projectId}/eval-datasets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(ds),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Failed to create dataset')
  }
  return res.json()
}

export async function getEvalDataset(datasetId: string): Promise<EvalDatasetDetail> {
  const res = await fetch(`${API_URL}/eval-datasets/${datasetId}`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load dataset')
  return res.json()
}

export async function runEval(datasetId: string): Promise<EvalRun> {
  const res = await fetch(`${API_URL}/eval-datasets/${datasetId}/run`, {
    method: 'POST',
    headers: await authHeaders(),
    signal: AbortSignal.timeout(180_000),
  })
  if (!res.ok) throw new Error('Evaluation run failed')
  return res.json()
}

export async function listEvalRuns(datasetId: string): Promise<EvalRunSummary[]> {
  const res = await fetch(`${API_URL}/eval-datasets/${datasetId}/runs`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to load runs')
  return res.json()
}

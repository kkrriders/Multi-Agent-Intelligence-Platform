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
export type Run = {
  id: string
  status: string
  output: string | null
  events: RunEvent[]
  citations?: Citation[]
  guardrails?: GuardrailEvent[]
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

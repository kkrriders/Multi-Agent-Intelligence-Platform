import { supabase } from './supabaseClient'

export type Project = { id: string; name: string; created_at: string }
export type RunEvent = { id: string; step_name: string; payload: Record<string, unknown>; created_at: string }
export type Run = { id: string; status: string; output: string | null; events: RunEvent[] }

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

export async function createRun(conversationId: string, input: string): Promise<Run> {
  const res = await fetch(`${API_URL}/conversations/${conversationId}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ input }),
  })
  if (!res.ok) throw new Error('Failed to create run')
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

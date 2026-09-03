'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  createConversation,
  createRun,
  listConversationRuns,
  listConversations,
  listPromptTemplates,
  type Conversation,
  type PromptTemplate,
  type Run,
} from '@/lib/api'
import { EmptyState, Notice } from './PanelKit'
import Timeline from './Timeline'

export default function ChatPanel({ projectId }: { projectId: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [message, setMessage] = useState('')
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [templateId, setTemplateId] = useState('')
  const [vars, setVars] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [blocked, setBlocked] = useState<string | null>(null)
  const skipNextFetch = useRef(false)

  const activeTemplate = templates.find((t) => t.id === templateId) ?? null

  useEffect(() => {
    listPromptTemplates(projectId).then(setTemplates).catch(() => setTemplates([]))
  }, [projectId])

  useEffect(() => {
    listConversations(projectId)
      .then((list) => {
        setConversations(list)
        if (list.length > 0) setConversationId(list[0].id)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load conversations'))
  }, [projectId])

  useEffect(() => {
    if (!conversationId) return
    if (skipNextFetch.current) {
      skipNextFetch.current = false
      return
    }
    listConversationRuns(conversationId)
      .then(setRuns)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load conversation'))
  }, [conversationId])

  async function handleNewConversation() {
    setError(null)
    try {
      const conversation = await createConversation(projectId)
      setConversations((prev) => [conversation, ...prev])
      skipNextFetch.current = true
      setRuns([])
      setConversationId(conversation.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create conversation')
    }
  }

  async function handleSend() {
    if (!activeTemplate && !message.trim()) return
    setLoading(true)
    setError(null)
    setBlocked(null)
    try {
      let activeId = conversationId
      if (!activeId) {
        const conversation = await createConversation(projectId)
        setConversations((prev) => [conversation, ...prev])
        skipNextFetch.current = true
        setConversationId(conversation.id)
        activeId = conversation.id
      }
      const result = activeTemplate
        ? await createRun(activeId, { template_id: activeTemplate.id, variables: vars })
        : await createRun(activeId, message)
      setRuns((prev) => [...prev, result])
      setMessage('')
      setVars({})
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to send message'
      if (msg.startsWith('blocked by guardrail')) {
        setBlocked(msg)
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  const latestRun = runs[runs.length - 1]

  return (
    <div className="flex flex-col gap-4">
      <div className="punch-corner-lg card-stack-shadow flex flex-col gap-3 border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="conversation-select" className="sr-only">
            Conversation
          </label>
          <select
            id="conversation-select"
            value={conversationId ?? ''}
            onChange={(e) => {
              const next = e.target.value || null
              if (!next) setRuns([])
              setConversationId(next)
            }}
            className="punch-corner-sm border border-border bg-background px-2 py-1 text-sm"
          >
            <option value="">New conversation</option>
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={handleNewConversation}>
            New conversation
          </Button>
          {templates.length > 0 && (
            <>
              <label
                htmlFor="template-select"
                className="ml-auto text-[0.7rem] tracking-wide text-muted-foreground uppercase"
              >
                Template
              </label>
              <select
                id="template-select"
                aria-label="Template"
                value={templateId}
                onChange={(e) => {
                  setTemplateId(e.target.value)
                  setVars({})
                }}
                className="punch-corner-sm border border-border bg-background px-2 py-1 text-sm"
              >
                <option value="">(free text)</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-end gap-2">
          {activeTemplate ? (
            activeTemplate.variables.map((v) => (
              <label key={v} className="flex flex-col gap-1 text-xs">
                <span className="font-mono">{v}</span>
                <Input
                  aria-label={`var ${v}`}
                  value={vars[v] ?? ''}
                  onChange={(e) => setVars((prev) => ({ ...prev, [v]: e.target.value }))}
                />
              </label>
            ))
          ) : (
            <>
              <label htmlFor="chat-message" className="sr-only">
                Message
              </label>
              <Input
                id="chat-message"
                className="flex-1"
                placeholder="Ask the agent something, or describe a task…"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </>
          )}
          <Button onClick={handleSend} disabled={loading}>
            {loading ? 'Sending…' : 'Send'}
          </Button>
        </div>
      </div>

      {error && <Notice>{error}</Notice>}
      {blocked && (
        <p
          role="status"
          className="punch-corner border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {blocked}
        </p>
      )}

      {runs.length > 0 ? (
        <div className="flex flex-col gap-4">
          {runs.map((run) => (
            <div
              key={run.id}
              className="punch-corner-lg card-stack-shadow border border-secondary/50 bg-card p-4"
            >
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-secondary-tint uppercase">
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-secondary" />
                Agent thread
              </p>
              <p>{run.output}</p>
              {run.citations && run.citations.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-2">
                  {run.citations.map((citation) => (
                    <li
                      key={citation.index}
                      className="border border-border bg-muted px-2 py-1 text-xs text-muted-foreground"
                    >
                      [{citation.index}] {citation.filename}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          {latestRun && <Timeline events={latestRun.events} guardrails={latestRun.guardrails} />}
        </div>
      ) : (
        <EmptyState
          title="No runs in this conversation yet"
          description="Send a message above to run it through guardrails, memory recall, retrieval, orchestration, and cost tracking. The agent's answer and a step-by-step execution timeline appear here."
        />
      )}
    </div>
  )
}

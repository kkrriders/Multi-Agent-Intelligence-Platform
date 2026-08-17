'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  createConversation,
  createRun,
  listConversationRuns,
  listConversations,
  type Conversation,
  type Run,
} from '@/lib/api'
import Timeline from './Timeline'

export default function ChatPanel({ projectId }: { projectId: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const skipNextFetch = useRef(false)

  useEffect(() => {
    listConversations(projectId)
      .then((list) => {
        setConversations(list)
        if (list.length > 0) setConversationId(list[0].id)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load conversations'))
  }, [projectId])

  useEffect(() => {
    if (!conversationId) {
      setRuns([])
      return
    }
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
    if (!message.trim()) return
    setLoading(true)
    setError(null)
    try {
      let activeId = conversationId
      if (!activeId) {
        const conversation = await createConversation(projectId)
        setConversations((prev) => [conversation, ...prev])
        skipNextFetch.current = true
        setConversationId(conversation.id)
        activeId = conversation.id
      }
      const result = await createRun(activeId, message)
      setRuns((prev) => [...prev, result])
      setMessage('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message')
    } finally {
      setLoading(false)
    }
  }

  const latestRun = runs[runs.length - 1]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <label htmlFor="conversation-select" className="sr-only">Conversation</label>
        <select
          id="conversation-select"
          value={conversationId ?? ''}
          onChange={(e) => setConversationId(e.target.value || null)}
          className="border border-border bg-card px-2 py-1 text-sm"
        >
          <option value="">New conversation</option>
          {conversations.map((c) => (
            <option key={c.id} value={c.id}>{c.title}</option>
          ))}
        </select>
        <Button variant="outline" size="sm" onClick={handleNewConversation}>
          New conversation
        </Button>
      </div>

      <div className="flex gap-2">
        <label htmlFor="chat-message" className="sr-only">Message</label>
        <Input id="chat-message" value={message} onChange={(e) => setMessage(e.target.value)} />
        <Button onClick={handleSend} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {runs.length > 0 && (
        <div className="flex flex-col gap-4">
          {runs.map((run) => (
            <div key={run.id} className="punch-corner-lg card-stack-shadow border border-secondary/50 bg-card p-4">
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-secondary-tint uppercase">
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-secondary" />
                Agent thread
              </p>
              <p>{run.output}</p>
            </div>
          ))}
          {latestRun && <Timeline events={latestRun.events} />}
        </div>
      )}
    </div>
  )
}

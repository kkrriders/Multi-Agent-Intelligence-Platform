'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { listConversations, searchMemories, type Conversation, type MemorySearchResult } from '@/lib/api'

export default function MemoryExplorerPanel({ projectId }: { projectId: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MemorySearchResult[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listConversations(projectId)
      .then(setConversations)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load conversations'))
  }, [projectId])

  async function handleSearch() {
    if (!query.trim()) return
    setError(null)
    try {
      setResults(await searchMemories(projectId, query))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search memory')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <div>
        <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Conversations</h2>
        <ul className="flex flex-col gap-1">
          {conversations.map((c) => (
            <li key={c.id} className="punch-corner border border-border bg-card p-2 text-sm">
              {c.title}
            </li>
          ))}
        </ul>
      </div>

      <div className="punch-corner-lg card-stack-shadow flex flex-col gap-2 border border-border bg-card p-4">
        <label htmlFor="memory-search" className="text-xs tracking-wide text-muted-foreground uppercase">
          Search memory
        </label>
        <div className="flex gap-2">
          <Input id="memory-search" value={query} onChange={(e) => setQuery(e.target.value)} />
          <Button onClick={handleSearch}>Search</Button>
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {results.map((r) => (
          <li key={r.run_id} className="punch-corner border border-border bg-card p-3 text-sm">
            <p className="font-mono text-xs text-muted-foreground">score: {r.score.toFixed(2)}</p>
            <p><span className="font-semibold">User:</span> {r.input}</p>
            <p><span className="font-semibold">Assistant:</span> {r.output}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}

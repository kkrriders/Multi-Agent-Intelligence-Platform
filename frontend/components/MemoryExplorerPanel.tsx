'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  listConversations,
  searchMemories,
  type Conversation,
  type MemorySearchResult,
} from '@/lib/api'
import { EmptyState, Notice, PanelSection, SkeletonRows } from './PanelKit'

export default function MemoryExplorerPanel({ projectId }: { projectId: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MemorySearchResult[]>([])
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listConversations(projectId)
      .then(setConversations)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load conversations'))
      .finally(() => setLoading(false))
  }, [projectId])

  async function handleSearch() {
    if (!query.trim()) return
    setError(null)
    try {
      setResults(await searchMemories(projectId, query))
      setSearched(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search memory')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {error && <Notice>{error}</Notice>}

      <PanelSection title="Conversations">
        {loading ? (
          <SkeletonRows rows={2} />
        ) : conversations.length === 0 ? (
          <EmptyState
            title="No conversations yet"
            description="Conversation threads are created from the Chat / Run panel. Each one keeps its own message history, which is replayed into the prompt on every run."
          />
        ) : (
          <ul className="flex flex-col gap-1">
            {conversations.map((c) => (
              <li
                key={c.id}
                className="punch-corner border border-border bg-card p-2 text-sm"
              >
                {c.title}
              </li>
            ))}
          </ul>
        )}
      </PanelSection>

      <PanelSection title="Semantic recall">
        <div className="punch-corner-lg card-stack-shadow flex flex-col gap-2 border border-border bg-card p-4">
          <label
            htmlFor="memory-search"
            className="text-xs tracking-wide text-muted-foreground uppercase"
          >
            Search memory
          </label>
          <div className="flex gap-2">
            <Input
              id="memory-search"
              className="flex-1"
              placeholder="Search past runs by meaning…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Button onClick={handleSearch}>Search</Button>
          </div>
        </div>

        {results.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {results.map((r) => (
              <li
                key={r.run_id}
                className="punch-corner border border-border bg-card p-3 text-sm"
              >
                <p className="font-mono text-xs text-muted-foreground">score: {r.score.toFixed(2)}</p>
                <p>
                  <span className="font-semibold">User:</span> {r.input}
                </p>
                <p>
                  <span className="font-semibold">Assistant:</span> {r.output}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title={searched ? 'No matches' : 'Search this project’s run history'}
            description={
              searched
                ? 'No stored run was close enough in meaning to that query. Try different wording, or run more turns to build up memory.'
                : "Every completed run is embedded and stored. Search retrieves the closest past turns by meaning — not keyword — the same recall the agent gets during a run."
            }
          />
        )}
      </PanelSection>
    </div>
  )
}

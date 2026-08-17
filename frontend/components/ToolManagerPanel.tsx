'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { createTool, invokeTool, listTools, type Tool } from '@/lib/api'

export default function ToolManagerPanel({ projectId }: { projectId: string }) {
  const [tools, setTools] = useState<Tool[]>([])
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, { status: string; latencyMs: number }>>({})

  useEffect(() => {
    listTools(projectId)
      .then(setTools)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load tools'))
  }, [projectId])

  async function handleRegister() {
    if (!name.trim() || !url.trim()) return
    setError(null)
    try {
      const tool = await createTool(projectId, { name, type: 'rest', config: { url, method: 'GET' } })
      setTools((prev) => [tool, ...prev])
      setName('')
      setUrl('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register tool')
    }
  }

  async function handleTest(tool: Tool) {
    const start = Date.now()
    try {
      const result = await invokeTool(tool.id, {})
      setResults((prev) => ({
        ...prev,
        [tool.id]: { status: `${result.status}`, latencyMs: Date.now() - start },
      }))
    } catch {
      setResults((prev) => ({
        ...prev,
        [tool.id]: { status: 'error', latencyMs: Date.now() - start },
      }))
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <ul className="flex flex-col gap-2">
        {tools.map((tool) => (
          <li
            key={tool.id}
            className="punch-corner flex items-center justify-between gap-4 border border-border bg-card p-3"
          >
            <div>
              <p className="font-mono text-sm">{tool.name}</p>
              <p className="text-xs text-muted-foreground">{tool.type}</p>
              {Object.keys(tool.permissions).length > 0 && (
                <p className="text-xs text-muted-foreground">
                  permissions: {JSON.stringify(tool.permissions)}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3">
              {results[tool.id] && (
                <>
                  <span className="font-mono text-xs text-muted-foreground">
                    {results[tool.id].status}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {results[tool.id].latencyMs}ms
                  </span>
                </>
              )}
              <Button variant="outline" size="sm" onClick={() => handleTest(tool)}>
                Test
              </Button>
            </div>
          </li>
        ))}
      </ul>

      <div className="punch-corner-lg card-stack-shadow flex flex-col gap-2 border border-border bg-card p-4">
        <label htmlFor="tool-name" className="text-xs tracking-wide text-muted-foreground uppercase">
          Name
        </label>
        <Input id="tool-name" value={name} onChange={(e) => setName(e.target.value)} />
        <label htmlFor="tool-url" className="mt-1 text-xs tracking-wide text-muted-foreground uppercase">
          URL
        </label>
        <Input id="tool-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
        <Button className="mt-2 self-start" onClick={handleRegister}>
          Register tool
        </Button>
      </div>
    </div>
  )
}

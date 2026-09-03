'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { createTool, invokeTool, listTools, type Tool } from '@/lib/api'
import { EmptyState, Notice, PanelSection, SkeletonRows } from './PanelKit'

export default function ToolManagerPanel({ projectId }: { projectId: string }) {
  const [tools, setTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [paramsText, setParamsText] = useState('')
  const [paramsError, setParamsError] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, { status: string; latencyMs: number }>>({})

  useEffect(() => {
    listTools(projectId)
      .then(setTools)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load tools'))
      .finally(() => setLoading(false))
  }, [projectId])

  async function handleRegister() {
    if (!name.trim() || !url.trim()) return
    setError(null)

    const config: Record<string, unknown> = { url, method: 'GET' }
    if (paramsText.trim()) {
      try {
        config.parameters = JSON.parse(paramsText)
      } catch {
        setParamsError('Parameters must be valid JSON')
        return
      }
    }
    setParamsError('')

    try {
      const tool = await createTool(projectId, { name, type: 'rest', config })
      setTools((prev) => [tool, ...prev])
      setName('')
      setUrl('')
      setParamsText('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register tool')
    }
  }

  async function handleTest(tool: Tool) {
    // Event handler, not render — wall-clock latency for the result readout.
    // eslint-disable-next-line react-hooks/purity
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
      {error && <Notice>{error}</Notice>}

      <PanelSection title="Registered tools">
        {loading ? (
          <SkeletonRows />
        ) : tools.length === 0 ? (
          <EmptyState
            title="No tools registered"
            description="Register a GET REST endpoint below and the agent can call it during a run. Only GET requests are exposed to the model — it never chooses the URL or headers. Use Test to fire a dry invoke and see the status and latency."
          />
        ) : (
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
        )}
      </PanelSection>

      <PanelSection title="Register a tool">
        <div className="punch-corner-lg card-stack-shadow flex flex-col gap-2 border border-border bg-card p-4">
          <label htmlFor="tool-name" className="text-xs tracking-wide text-muted-foreground uppercase">
            Name
          </label>
          <Input id="tool-name" value={name} onChange={(e) => setName(e.target.value)} />
          <label
            htmlFor="tool-url"
            className="mt-1 text-xs tracking-wide text-muted-foreground uppercase"
          >
            URL
          </label>
          <Input
            id="tool-url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
          />
          <label
            htmlFor="tool-params"
            className="mt-1 text-xs tracking-wide text-muted-foreground uppercase"
          >
            Parameters (JSON Schema)
          </label>
          <textarea
            id="tool-params"
            value={paramsText}
            onChange={(e) => setParamsText(e.target.value)}
            placeholder='{"type":"object","properties":{}}'
            rows={3}
            className="punch-corner border border-border bg-background p-2 font-mono text-xs"
          />
          {paramsError && <p className="text-sm text-destructive">{paramsError}</p>}
          <Button className="mt-2 self-start" onClick={handleRegister}>
            Register tool
          </Button>
        </div>
      </PanelSection>
    </div>
  )
}

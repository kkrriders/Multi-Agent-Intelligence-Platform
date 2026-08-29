'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  createPromptTemplate,
  listPromptTemplateVersions,
  listPromptTemplates,
  runTemplateTest,
  updatePromptTemplate,
  type PromptTemplate,
  type PromptTemplateVersion,
  type Run,
} from '@/lib/api'

export default function PromptManagerPanel({ projectId }: { projectId: string }) {
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newBody, setNewBody] = useState('')
  const [editBody, setEditBody] = useState('')
  const [versions, setVersions] = useState<PromptTemplateVersion[]>([])
  const [testVars, setTestVars] = useState<Record<string, string>>({})
  const [testRun, setTestRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)

  const selected = templates.find((t) => t.id === selectedId) ?? null

  useEffect(() => {
    listPromptTemplates(projectId)
      .then((list) => {
        setTemplates(list)
        setSelectedId((cur) => cur ?? list[0]?.id ?? null)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load templates'))
  }, [projectId])

  useEffect(() => {
    if (!selected) return
    setEditBody(selected.body)
    setTestVars({})
    setTestRun(null)
    listPromptTemplateVersions(selected.id).then(setVersions).catch(() => setVersions([]))
  }, [selectedId, selected])

  async function handleCreate() {
    if (!newName.trim() || !newBody.trim()) return
    try {
      const created = await createPromptTemplate(projectId, { name: newName, body: newBody })
      setTemplates((prev) => [created, ...prev])
      setSelectedId(created.id)
      setCreating(false)
      setNewName('')
      setNewBody('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create template')
    }
  }

  async function handleSaveVersion() {
    if (!selected) return
    try {
      const version = await updatePromptTemplate(selected.id, { body: editBody })
      setVersions((prev) => [version, ...prev])
      setTemplates((prev) =>
        prev.map((t) =>
          t.id === selected.id
            ? { ...t, body: version.body, version: version.version, variables: version.variables, version_count: t.version_count + 1 }
            : t
        )
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save version')
    }
  }

  async function handleTest() {
    if (!selected) return
    try {
      const run = await runTemplateTest(projectId, selected.id, testVars)
      setTestRun(run)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Test run failed')
    }
  }

  return (
    <div className="flex flex-col gap-4 sm:flex-row">
      <div className="flex shrink-0 flex-col gap-2 sm:w-64">
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button size="sm" variant="outline" onClick={() => setCreating((c) => !c)}>
          New template
        </Button>
        {creating && (
          <div className="punch-corner flex flex-col gap-2 border border-border bg-card p-3">
            <label htmlFor="new-name" className="text-xs tracking-wide text-muted-foreground uppercase">
              Template name
            </label>
            <Input id="new-name" value={newName} onChange={(e) => setNewName(e.target.value)} />
            <label htmlFor="new-body" className="text-xs tracking-wide text-muted-foreground uppercase">
              Template body
            </label>
            <textarea
              id="new-body"
              value={newBody}
              onChange={(e) => setNewBody(e.target.value)}
              rows={3}
              className="punch-corner border border-border bg-background p-2 font-mono text-xs"
              placeholder="Summarize {{topic}} for a {{audience}} reader."
            />
            <Button size="sm" onClick={handleCreate}>
              Create
            </Button>
          </div>
        )}
        <ul className="flex flex-col gap-1">
          {templates.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => setSelectedId(t.id)}
                className={`w-full border border-border p-2 text-left font-mono text-xs ${
                  t.id === selectedId ? 'border-primary font-bold' : 'hover:bg-muted'
                }`}
              >
                {t.name} · v{t.version} · {t.variables.length} var{t.variables.length === 1 ? '' : 's'}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {selected && (
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <div className="punch-corner-lg card-stack-shadow flex flex-col gap-2 border border-border bg-card p-4">
            <label htmlFor="edit-body" className="text-xs tracking-wide text-muted-foreground uppercase">
              Template body
            </label>
            <textarea
              id="edit-body"
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
              rows={4}
              className="punch-corner border border-border bg-background p-2 font-mono text-xs"
            />
            <Button size="sm" className="self-start" onClick={handleSaveVersion}>
              Save as new version
            </Button>
          </div>

          <div className="punch-corner-lg card-stack-shadow border border-border bg-card p-4">
            <p className="mb-2 text-xs tracking-wide text-muted-foreground uppercase">Version history</p>
            <ul className="flex flex-col gap-1">
              {versions.map((v) => (
                <li key={v.id} className="font-mono text-xs">
                  <details>
                    <summary className="cursor-pointer">
                      v{v.version} · {new Date(v.created_at).toLocaleString()}
                    </summary>
                    <pre className="mt-1 overflow-x-auto text-muted-foreground">{v.body}</pre>
                  </details>
                </li>
              ))}
            </ul>
          </div>

          <div className="punch-corner-lg card-stack-shadow flex flex-col gap-2 border border-border bg-card p-4">
            <p className="text-xs tracking-wide text-muted-foreground uppercase">Test</p>
            {selected.variables.map((v) => (
              <label key={v} className="flex flex-col gap-1 text-xs">
                <span className="font-mono">{v}</span>
                <Input
                  aria-label={`var ${v}`}
                  value={testVars[v] ?? ''}
                  onChange={(e) => setTestVars((prev) => ({ ...prev, [v]: e.target.value }))}
                />
              </label>
            ))}
            <Button size="sm" className="self-start" onClick={handleTest}>
              Run test
            </Button>
            {testRun && (
              <div
                data-testid="test-output"
                className="punch-corner border border-border bg-background p-2 text-sm"
              >
                {testRun.output}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

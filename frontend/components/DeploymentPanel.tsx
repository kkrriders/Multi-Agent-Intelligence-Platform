'use client'

import { useEffect, useRef, useState } from 'react'
import {
  createDeployTarget,
  createDeployment,
  deleteDeployTarget,
  getLimits,
  listDeployTargets,
  listDeployments,
  type Deployment,
  type DeployTarget,
} from '@/lib/api'

const COMPONENTS = ['backend', 'frontend'] as const

export default function DeploymentPanel() {
  const [apiEnabled, setApiEnabled] = useState(false)
  const [targets, setTargets] = useState<DeployTarget[]>([])
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [imageRepo, setImageRepo] = useState('')
  const [registry, setRegistry] = useState('ghcr.io')

  const [targetId, setTargetId] = useState('')
  const [components, setComponents] = useState<string[]>(['backend', 'frontend'])
  const [building, setBuilding] = useState(false)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  async function refreshDeployments() {
    const ds = await listDeployments()
    setDeployments(ds)
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    if (ds.some((d) => d.status === 'running')) {
      pollRef.current = setInterval(() => void refreshDeployments(), 5000)
    }
  }

  async function refreshTargets() {
    const ts = await listDeployTargets()
    setTargets(ts)
    setTargetId((cur) => cur || ts[0]?.id || '')
  }

  useEffect(() => {
    getLimits()
      .then((l) => setApiEnabled(l.deploy_api_enabled))
      .catch(() => setApiEnabled(false))
    listDeployTargets()
      .then((ts) => {
        setTargets(ts)
        setTargetId((cur) => cur || ts[0]?.id || '')
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load deploy targets'))
    listDeployments()
      .then((ds) => {
        setDeployments(ds)
        if (ds.some((d) => d.status === 'running')) {
          pollRef.current = setInterval(() => void refreshDeployments(), 5000)
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load deployments'))
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function addTarget() {
    setError(null)
    try {
      await createDeployTarget({ name, image_repo: imageRepo, registry })
      setName('')
      setImageRepo('')
      await refreshTargets()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add target')
    }
  }

  async function removeTarget(id: string) {
    await deleteDeployTarget(id)
    await refreshTargets()
  }

  async function build() {
    if (!targetId) return
    setBuilding(true)
    setError(null)
    try {
      await createDeployment({ target_id: targetId, components })
      await refreshDeployments()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start deployment')
    } finally {
      setBuilding(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <section>
        <h2 className="font-heading text-sm font-bold uppercase mb-3">Deploy targets</h2>
        <ul className="mb-3 flex flex-col gap-1">
          {targets.map((t) => (
            <li key={t.id} className="flex items-center justify-between border border-border p-2 font-mono text-xs">
              <span>
                {t.name} · {t.registry}/{t.image_repo}
              </span>
              <button
                type="button"
                aria-label={`Delete ${t.name}`}
                onClick={() => removeTarget(t.id)}
                className="text-destructive hover:underline"
              >
                delete
              </button>
            </li>
          ))}
          {targets.length === 0 && <li className="text-sm text-muted-foreground">No targets yet.</li>}
        </ul>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="flex flex-col font-mono text-[0.65rem] text-muted-foreground">
            target name
            <input
              aria-label="target name"
              className="border border-border bg-background p-1 text-sm text-foreground"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label className="flex flex-col font-mono text-[0.65rem] text-muted-foreground">
            registry
            <input
              aria-label="registry"
              className="border border-border bg-background p-1 text-sm text-foreground"
              value={registry}
              onChange={(e) => setRegistry(e.target.value)}
            />
          </label>
          <label className="flex flex-1 flex-col font-mono text-[0.65rem] text-muted-foreground">
            image repo
            <input
              aria-label="image repo"
              className="border border-border bg-background p-1 text-sm text-foreground"
              value={imageRepo}
              onChange={(e) => setImageRepo(e.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={addTarget}
            className="border border-border px-3 py-1 font-mono text-xs hover:bg-muted"
          >
            Add target
          </button>
        </div>
      </section>

      <section>
        <h2 className="font-heading text-sm font-bold uppercase mb-3">Build &amp; publish</h2>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <select
            aria-label="deploy target"
            className="border border-border bg-background p-1 text-sm text-foreground"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
          >
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          {COMPONENTS.map((c) => (
            <label key={c} className="flex items-center gap-1 font-mono text-xs">
              <input
                type="checkbox"
                checked={components.includes(c)}
                onChange={(e) =>
                  setComponents((cur) => (e.target.checked ? [...cur, c] : cur.filter((x) => x !== c)))
                }
              />
              {c}
            </label>
          ))}
          <button
            type="button"
            onClick={build}
            disabled={!apiEnabled || building || !targetId || components.length === 0}
            className="border border-border px-3 py-1 font-mono text-xs hover:bg-muted disabled:opacity-50"
          >
            {building ? 'Building…' : 'Build & Publish'}
          </button>
        </div>
        {!apiEnabled && (
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            Deploy API is disabled on this server (set ENABLE_DEPLOY_API=true and mount the docker
            socket). Target config is still saved for a manual deploy.
          </p>
        )}
      </section>

      <section>
        <h2 className="font-heading text-sm font-bold uppercase mb-2">Deployment history</h2>
        {deployments.length === 0 ? (
          <p className="text-sm text-muted-foreground">No deployments yet.</p>
        ) : (
          <ul className="flex flex-col gap-1 font-mono text-xs">
            {deployments.map((d) => (
              <li key={d.id} className="border border-border p-2">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span>{new Date(d.created_at).toLocaleString()}</span>
                  <span className="font-bold">{d.image_tag}</span>
                  <span className="text-muted-foreground">{d.git_sha?.slice(0, 7)}</span>
                  <span className="text-muted-foreground">{d.components.join(', ')}</span>
                  <span
                    className={
                      d.status === 'failed'
                        ? 'text-destructive'
                        : d.status === 'succeeded'
                          ? 'text-primary'
                          : 'text-muted-foreground'
                    }
                  >
                    {d.status}
                  </span>
                </div>
                {d.log && (
                  <details className="mt-1">
                    <summary className="cursor-pointer text-muted-foreground">log</summary>
                    <pre className="overflow-x-auto text-muted-foreground">{d.log}</pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

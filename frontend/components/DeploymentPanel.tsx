'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import { EmptyState, Notice, PanelSection } from './PanelKit'

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
      {error && <Notice>{error}</Notice>}

      <PanelSection title="Deploy targets">
        {targets.length === 0 ? (
          <EmptyState
            title="No targets yet"
            description="A target names where built images are pushed — a registry, an image repo, and its env-var set. Add one below; the config is stored even when the in-app build API is off, so you can deploy the published images by hand."
          />
        ) : (
          <ul className="flex flex-col gap-1">
            {targets.map((t) => (
              <li
                key={t.id}
                className="punch-corner flex items-center justify-between border border-border bg-card p-2 font-mono text-xs"
              >
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
          </ul>
        )}
        <div className="punch-corner-lg card-stack-shadow flex flex-col gap-3 border border-border bg-card p-4 sm:flex-row sm:items-end">
          <label className="flex flex-col gap-1 font-mono text-[0.65rem] text-muted-foreground">
            target name
            <Input aria-label="target name" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 font-mono text-[0.65rem] text-muted-foreground">
            registry
            <Input
              aria-label="registry"
              value={registry}
              onChange={(e) => setRegistry(e.target.value)}
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 font-mono text-[0.65rem] text-muted-foreground">
            image repo
            <Input
              aria-label="image repo"
              value={imageRepo}
              onChange={(e) => setImageRepo(e.target.value)}
            />
          </label>
          <Button variant="outline" size="sm" onClick={addTarget}>
            Add target
          </Button>
        </div>
      </PanelSection>

      <PanelSection title="Build & publish">
        <div className="punch-corner-lg card-stack-shadow flex flex-col gap-3 border border-border bg-card p-4 sm:flex-row sm:items-center">
          <select
            aria-label="deploy target"
            className="punch-corner-sm border border-border bg-background p-1 text-sm text-foreground"
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
                  setComponents((cur) =>
                    e.target.checked ? [...cur, c] : cur.filter((x) => x !== c)
                  )
                }
              />
              {c}
            </label>
          ))}
          <Button
            variant="outline"
            size="sm"
            onClick={build}
            disabled={!apiEnabled || building || !targetId || components.length === 0}
          >
            {building ? 'Building…' : 'Build & Publish'}
          </Button>
        </div>
        {!apiEnabled && (
          <p className="font-mono text-xs text-muted-foreground">
            Deploy API is disabled on this server (set ENABLE_DEPLOY_API=true and mount the docker
            socket). Target config is still saved for a manual deploy.
          </p>
        )}
      </PanelSection>

      <PanelSection title="Deployment history">
        {deployments.length === 0 ? (
          <EmptyState
            title="No deployments yet"
            description="Each build records its image tag, git SHA, the components built, status, and the full build log. Runs in progress refresh automatically."
          />
        ) : (
          <ul className="flex flex-col gap-1 font-mono text-xs">
            {deployments.map((d) => (
              <li key={d.id} className="punch-corner border border-border bg-card p-2">
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
      </PanelSection>
    </div>
  )
}

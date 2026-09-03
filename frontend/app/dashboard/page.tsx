'use client'

import { useEffect, useState } from 'react'
import { createProject, listProjects, type Project } from '@/lib/api'
import ProjectList from '@/components/ProjectList'
import AppHeader from '@/components/AppHeader'
import { Notice, SkeletonRows } from '@/components/PanelKit'

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load projects'))
      .finally(() => setLoading(false))
  }, [])

  async function handleCreate(name: string) {
    if (!name.trim()) return
    setError(null)
    try {
      const project = await createProject(name)
      setProjects((prev) => [project, ...prev])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project')
    }
  }

  return (
    <>
      <AppHeader />
      <main className="mx-auto w-full min-w-0 max-w-2xl px-6 py-16">
        <h1 className="mb-2 font-heading text-2xl font-bold uppercase">Projects</h1>
        <p className="mb-6 text-sm text-muted-foreground">
          Each project is one AI application — its own documents, tools, prompts, guardrail policy,
          and run history.
        </p>
        {error && (
          <div className="mb-4">
            <Notice>{error}</Notice>
          </div>
        )}
        {loading ? <SkeletonRows rows={3} /> : <ProjectList projects={projects} onCreate={handleCreate} />}
      </main>
    </>
  )
}

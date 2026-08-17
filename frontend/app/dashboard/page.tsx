'use client'

import { useEffect, useState } from 'react'
import { createProject, listProjects, type Project } from '@/lib/api'
import ProjectList from '@/components/ProjectList'
import AppHeader from '@/components/AppHeader'

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load projects'))
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
        <h1 className="font-heading text-2xl font-bold uppercase mb-6">Projects</h1>
        {error && <p className="mb-4 text-sm text-destructive">{error}</p>}
        <ProjectList projects={projects} onCreate={handleCreate} />
      </main>
    </>
  )
}

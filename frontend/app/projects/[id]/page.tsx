import Link from 'next/link'
import ProjectWorkspace from '@/components/ProjectWorkspace'
import AppHeader from '@/components/AppHeader'

export default async function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return (
    <>
      <AppHeader />
      <main className="mx-auto w-full min-w-0 max-w-5xl px-6 py-16">
        <Link
          href="/dashboard"
          className="inline-block text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          ← Projects
        </Link>
        <p className="mt-2 mb-6 max-w-2xl text-xs text-muted-foreground">
          Operator console — configure the pipeline, inspect runs, and watch cost here. Your own
          application drives the same pipeline through the REST API.
        </p>
        <ProjectWorkspace projectId={id} />
      </main>
    </>
  )
}

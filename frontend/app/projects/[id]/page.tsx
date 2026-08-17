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
          className="mb-6 inline-block text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          ← Projects
        </Link>
        <ProjectWorkspace projectId={id} />
      </main>
    </>
  )
}

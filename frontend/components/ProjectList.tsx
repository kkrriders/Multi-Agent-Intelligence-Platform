'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Project } from '@/lib/api'

type Props = {
  projects: Project[]
  onCreate: (name: string) => void
}

export default function ProjectList({ projects, onCreate }: Props) {
  const [name, setName] = useState('')

  return (
    <div className="flex flex-col gap-4">
      {projects.length === 0 && (
        <p className="text-sm text-muted-foreground">No projects yet — create one below.</p>
      )}
      <ul className="flex flex-col gap-2">
        {projects.map((project) => (
          <li key={project.id}>
            <Link
              href={`/projects/${project.id}`}
              className="punch-corner flex items-center justify-between gap-4 border border-border bg-card p-3 transition-colors hover:border-primary"
            >
              <span className="font-mono text-sm">{project.name}</span>
              <span className="text-xs text-muted-foreground">
                {new Date(project.created_at).toLocaleDateString()}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <label htmlFor="new-project-name" className="sr-only">New project name</label>
        <Input
          id="new-project-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New project name"
        />
        <Button
          onClick={() => {
            onCreate(name)
            setName('')
          }}
        >
          Create
        </Button>
      </div>
    </div>
  )
}

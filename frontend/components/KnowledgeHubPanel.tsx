'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { deleteDocument, listDocuments, uploadDocument, type Document } from '@/lib/api'

export default function KnowledgeHubPanel({ projectId }: { projectId: string }) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const hasLocalUpdate = useRef(false)

  useEffect(() => {
    listDocuments(projectId)
      .then((list) => {
        if (!hasLocalUpdate.current) setDocuments(list)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load documents'))
  }, [projectId])

  async function handleUpload() {
    const file = fileInputRef.current?.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const document = await uploadDocument(projectId, file)
      hasLocalUpdate.current = true
      setDocuments((prev) => [document, ...prev])
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload document')
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(documentId: string) {
    setError(null)
    try {
      await deleteDocument(projectId, documentId)
      hasLocalUpdate.current = true
      setDocuments((prev) => prev.filter((d) => d.id !== documentId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete document')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="punch-corner-lg card-stack-shadow flex items-center gap-2 border border-border bg-card p-4">
        <label htmlFor="document-file" className="text-xs tracking-wide text-muted-foreground uppercase">
          Upload document
        </label>
        <input
          id="document-file"
          ref={fileInputRef}
          type="file"
          accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
          className="text-sm"
        />
        <Button onClick={handleUpload} disabled={uploading}>
          {uploading ? 'Uploading...' : 'Upload'}
        </Button>
      </div>

      <ul className="flex flex-col gap-2">
        {documents.map((doc) => (
          <li
            key={doc.id}
            className="punch-corner flex items-center justify-between gap-4 border border-border bg-card p-3"
          >
            <div>
              <p className="font-mono text-sm">{doc.filename}</p>
              <p className="text-xs text-muted-foreground">
                {doc.status}
                {doc.error ? `: ${doc.error}` : ''}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => handleDelete(doc.id)}>
              Delete
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}

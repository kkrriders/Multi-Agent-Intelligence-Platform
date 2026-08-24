import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('./supabaseClient', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'test-token' } } }),
    },
  },
}))

describe('api client', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: '1', name: 'Test Project', created_at: '2026-01-01T00:00:00Z' }),
    }) as unknown as typeof fetch
  })

  it('createProject sends an authorized POST request', async () => {
    const { createProject } = await import('./api')
    const result = await createProject('Test Project')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
    expect(result.name).toBe('Test Project')
  })

  it('listTools sends an authorized GET request', async () => {
    const { listTools } = await import('./api')
    await listTools('project-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/tools'),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
  })

  it('createTool sends an authorized POST request with the tool payload', async () => {
    const { createTool } = await import('./api')
    await createTool('project-1', { name: 'Echo', type: 'rest', config: { url: 'https://example.com' } })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/tools'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        body: JSON.stringify({ name: 'Echo', type: 'rest', config: { url: 'https://example.com' } }),
      })
    )
  })

  it('invokeTool sends an authorized POST request to the invoke endpoint', async () => {
    const { invokeTool } = await import('./api')
    await invokeTool('tool-1', { foo: 'bar' })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/tools/tool-1/invoke'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        body: JSON.stringify({ foo: 'bar' }),
      })
    )
  })

  it('createConversation sends an authorized POST request', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'conv-1', project_id: 'project-1', title: 'New conversation', created_at: '2026-01-01T00:00:00Z' }),
    }) as unknown as typeof fetch

    const { createConversation } = await import('./api')
    await createConversation('project-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/conversations'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        body: JSON.stringify({}),
      })
    )
  })

  it('listConversations sends an authorized GET request', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch

    const { listConversations } = await import('./api')
    await listConversations('project-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/conversations'),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) })
    )
  })

  it('createRun posts to the conversation-scoped endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'run-1', status: 'completed', output: 'pong', events: [] }),
    }) as unknown as typeof fetch

    const { createRun } = await import('./api')
    await createRun('conv-1', 'ping')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/conversations/conv-1/runs'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ input: 'ping' }),
      })
    )
  })

  it('listConversationRuns sends an authorized GET request', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch

    const { listConversationRuns } = await import('./api')
    await listConversationRuns('conv-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/conversations/conv-1/runs'),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) })
    )
  })

  it('searchMemories sends an authorized GET request with the query', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch

    const { searchMemories } = await import('./api')
    await searchMemories('project-1', 'rocket codeword')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/memories/search?q=rocket%20codeword'),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) })
    )
  })

  it('uploadDocument sends an authorized multipart POST request', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'doc-1',
        project_id: 'project-1',
        filename: 'notes.txt',
        mime_type: 'text/plain',
        storage_path: 'project-1/doc-1/notes.txt',
        status: 'indexed',
        error: null,
        created_at: '2026-01-01T00:00:00Z',
      }),
    }) as unknown as typeof fetch

    const { uploadDocument } = await import('./api')
    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    await uploadDocument('project-1', file)

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/documents'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        body: expect.any(FormData),
      })
    )
  })

  it('listDocuments sends an authorized GET request', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch

    const { listDocuments } = await import('./api')
    await listDocuments('project-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/documents'),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) })
    )
  })

  it('deleteDocument sends an authorized DELETE request', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'deleted' }) }) as unknown as typeof fetch

    const { deleteDocument } = await import('./api')
    await deleteDocument('project-1', 'doc-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/documents/doc-1'),
      expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
  })
})

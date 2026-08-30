import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const getLimits = vi.fn()
const listDeployTargets = vi.fn()
const createDeployTarget = vi.fn()
const deleteDeployTarget = vi.fn()
const listDeployments = vi.fn()
const createDeployment = vi.fn()

vi.mock('@/lib/api', () => ({
  getLimits,
  listDeployTargets,
  createDeployTarget,
  deleteDeployTarget,
  listDeployments,
  createDeployment,
}))

function setup({ enabled = false } = {}) {
  getLimits.mockResolvedValue({ run_rate_limit_per_min: 20, deploy_api_enabled: enabled })
  listDeployTargets.mockResolvedValue([])
  listDeployments.mockResolvedValue([])
}

describe('DeploymentPanel', () => {
  it('adds a target via createDeployTarget', async () => {
    setup()
    createDeployTarget.mockResolvedValue({
      id: 't1', name: 'prod', registry: 'ghcr.io', image_repo: 'acme/app', config: {}, created_at: '',
    })
    const { default: DeploymentPanel } = await import('./DeploymentPanel')
    render(<DeploymentPanel />)

    fireEvent.change(await screen.findByLabelText(/target name/i), { target: { value: 'prod' } })
    fireEvent.change(screen.getByLabelText(/image repo/i), { target: { value: 'acme/app' } })
    fireEvent.click(screen.getByRole('button', { name: /add target/i }))

    await waitFor(() =>
      expect(createDeployTarget).toHaveBeenCalledWith(expect.objectContaining({ name: 'prod', image_repo: 'acme/app' })),
    )
  })

  it('disables Build & Publish with a note when the deploy API is off', async () => {
    setup({ enabled: false })
    listDeployTargets.mockResolvedValue([
      { id: 't1', name: 'prod', registry: 'ghcr.io', image_repo: 'acme/app', config: {}, created_at: '' },
    ])
    const { default: DeploymentPanel } = await import('./DeploymentPanel')
    render(<DeploymentPanel />)

    expect(await screen.findByText(/deploy api is disabled/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /build & publish/i })).toBeDisabled()
  })

  it('enables Build & Publish and calls createDeployment when the API is on', async () => {
    setup({ enabled: true })
    listDeployTargets.mockResolvedValue([
      { id: 't1', name: 'prod', registry: 'ghcr.io', image_repo: 'acme/app', config: {}, created_at: '' },
    ])
    createDeployment.mockResolvedValue({
      id: 'd1', target_id: 't1', image_tag: '2026-08-30-abc1234', git_sha: 'abc1234',
      components: ['backend'], status: 'succeeded', log: 'ok', created_at: '',
    })
    const { default: DeploymentPanel } = await import('./DeploymentPanel')
    render(<DeploymentPanel />)

    const btn = await screen.findByRole('button', { name: /build & publish/i })
    expect(btn).toBeEnabled()
    fireEvent.click(btn)
    await waitFor(() =>
      expect(createDeployment).toHaveBeenCalledWith(expect.objectContaining({ target_id: 't1' })),
    )
  })

  it('renders deployment history rows with status', async () => {
    setup()
    listDeployments.mockResolvedValue([
      {
        id: 'd1', target_id: 't1', image_tag: '2026-08-30-abc1234', git_sha: 'abc1234def',
        components: ['backend', 'frontend'], status: 'succeeded', log: '$ docker build ...', created_at: '2026-08-30T12:00:00Z',
      },
    ])
    const { default: DeploymentPanel } = await import('./DeploymentPanel')
    render(<DeploymentPanel />)

    expect(await screen.findByText('2026-08-30-abc1234')).toBeInTheDocument()
    expect(screen.getByText('succeeded')).toBeInTheDocument()
  })
})

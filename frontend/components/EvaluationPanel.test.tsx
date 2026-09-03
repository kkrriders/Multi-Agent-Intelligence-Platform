import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listEvalDatasets = vi.fn()
const createEvalDataset = vi.fn()
const getEvalDataset = vi.fn()
const runEval = vi.fn()
const listEvalRuns = vi.fn()

vi.mock('@/lib/api', () => ({ listEvalDatasets, createEvalDataset, getEvalDataset, runEval, listEvalRuns }))

const ds = (over = {}) => ({
  id: 'd1',
  name: 'basics',
  item_count: 2,
  latest_run: null,
  created_at: '2026-01-01T00:00:00Z',
  ...over,
})
const detail = (over = {}) => ({
  ...ds(),
  items: [
    { id: 'i1', input: '2+2?', expected: '4' },
    { id: 'i2', input: 'cap FR?', expected: 'Paris' },
  ],
  ...over,
})

describe('EvaluationPanel', () => {
  it('lists datasets with a latest-run badge', async () => {
    listEvalDatasets.mockResolvedValue([
      ds({
        latest_run: {
          id: 'r1',
          dataset_id: 'd1',
          item_count: 2,
          accuracy: 0.5,
          hallucination_rate: 0.5,
          mean_score: 0.6,
          created_at: '',
        },
      }),
    ])
    getEvalDataset.mockResolvedValue(detail())
    listEvalRuns.mockResolvedValue([])
    const { default: P } = await import('./EvaluationPanel')
    render(<P projectId="p1" />)
    await waitFor(() => expect(screen.getByText(/basics/)).toBeInTheDocument())
    expect(screen.getByText(/50%/)).toBeInTheDocument()
  })

  it('creates a dataset from entered rows', async () => {
    listEvalDatasets.mockResolvedValue([])
    createEvalDataset.mockResolvedValue(detail())
    const { default: P } = await import('./EvaluationPanel')
    render(<P projectId="p1" />)
    await waitFor(() => expect(listEvalDatasets).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /new dataset/i }))
    fireEvent.change(screen.getByLabelText(/dataset name/i), { target: { value: 'basics' } })
    fireEvent.change(screen.getByLabelText(/^input 1$/i), { target: { value: '2+2?' } })
    fireEvent.change(screen.getByLabelText(/^expected 1$/i), { target: { value: '4' } })
    fireEvent.click(screen.getByRole('button', { name: /^create dataset$/i }))
    await waitFor(() =>
      expect(createEvalDataset).toHaveBeenCalledWith('p1', { name: 'basics', items: [{ input: '2+2?', expected: '4' }] })
    )
  })

  it('runs an evaluation and shows the summary + results', async () => {
    listEvalDatasets.mockResolvedValue([ds()])
    getEvalDataset.mockResolvedValue(detail())
    listEvalRuns.mockResolvedValue([])
    runEval.mockResolvedValue({
      id: 'r9',
      dataset_id: 'd1',
      item_count: 2,
      accuracy: 1,
      hallucination_rate: 0,
      mean_score: 0.95,
      created_at: '',
      results: [
        { id: 'x1', item_id: 'i1', output: '4', score: 1, hallucinated: false, reason: 'exact' },
        { id: 'x2', item_id: 'i2', output: 'Paris', score: 0.9, hallucinated: false, reason: 'match' },
      ],
    })
    const { default: P } = await import('./EvaluationPanel')
    render(<P projectId="p1" />)
    await screen.findByText(/basics/)
    fireEvent.click(await screen.findByRole('button', { name: /run evaluation/i }))
    await waitFor(() => expect(runEval).toHaveBeenCalledWith('d1'))
    await waitFor(() => expect(screen.getByText(/accuracy 100%/i)).toBeInTheDocument())
    expect(screen.getByText('exact')).toBeInTheDocument()
    expect(screen.getByText('match')).toBeInTheDocument()
  })
})

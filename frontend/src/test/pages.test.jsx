import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from '../pages/Dashboard.jsx'
import Tasks from '../pages/Tasks.jsx'
import { api } from '../services/api.js'

vi.mock('../services/api.js', () => ({
  api: {
    getDashboard: vi.fn(),
    listTasks: vi.fn(),
    createTask: vi.fn(),
    completeTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}))

const renderPage = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)

beforeEach(() => vi.clearAllMocks())

describe('Dashboard', () => {
  it('renders counts and empty lists', async () => {
    api.getDashboard.mockResolvedValue({
      counts: { pending: 0, completed: 0, overdue: 0 },
      due_today: [],
      upcoming: [],
    })
    renderPage(<Dashboard />)
    expect(await screen.findByText('Nothing due today 🎉')).toBeInTheDocument()
    expect(screen.getByText('No upcoming tasks')).toBeInTheDocument()
    expect(screen.getByTestId('stat-pending')).toHaveTextContent('0')
  })

  it('shows an error state', async () => {
    api.getDashboard.mockRejectedValue(new Error('Cannot reach the server'))
    renderPage(<Dashboard />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the server')
  })
})

describe('Tasks', () => {
  it('renders the form and empty state', async () => {
    api.listTasks.mockResolvedValue([])
    renderPage(<Tasks />)
    expect(screen.getByLabelText('Title')).toBeInTheDocument()
    expect(await screen.findByText('No tasks yet')).toBeInTheDocument()
  })

  it('renders a list of tasks', async () => {
    api.listTasks.mockResolvedValue([
      { id: '1', title: 'Write report', description: null, status: 'pending', due_date: null },
    ])
    renderPage(<Tasks />)
    expect(await screen.findByText('Write report')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark Write report as complete' })).toBeEnabled()
  })
})

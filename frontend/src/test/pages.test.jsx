import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from '../pages/Dashboard.jsx'
import Documents from '../pages/Documents.jsx'
import Reminders from '../pages/Reminders.jsx'
import Tasks from '../pages/Tasks.jsx'
import { api } from '../services/api.js'

vi.mock('../services/api.js', () => ({
  api: {
    getDashboard: vi.fn(),
    listTasks: vi.fn(),
    createTask: vi.fn(),
    completeTask: vi.fn(),
    deleteTask: vi.fn(),
    listReminders: vi.fn(),
    createReminder: vi.fn(),
    updateReminder: vi.fn(),
    completeReminder: vi.fn(),
    deleteReminder: vi.fn(),
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
    getDocumentChunks: vi.fn(),
    searchDocuments: vi.fn(),
    getUnreadCount: vi.fn().mockResolvedValue({ unread_count: 0 }),
    listNotifications: vi.fn().mockResolvedValue([]),
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

describe('Reminders', () => {
  it('renders reminders header and empty state', async () => {
    api.listReminders.mockResolvedValue([])
    renderPage(<Reminders />)
    expect(await screen.findByText('No reminders found')).toBeInTheDocument()
    expect(screen.getByText('New Reminder')).toBeInTheDocument()
  })

  it('renders list of reminders', async () => {
    api.listReminders.mockResolvedValue([
      {
        id: 'rem-1',
        title: 'Submit tax return',
        description: 'Before the deadline',
        due_at: '2026-10-31T15:00:00Z',
        timezone: 'UTC',
        status: 'pending',
      },
    ])
    renderPage(<Reminders />)
    expect(await screen.findByText('Submit tax return')).toBeInTheDocument()
    expect(screen.getByText('Before the deadline')).toBeInTheDocument()
  })
})

describe('Documents', () => {
  it('renders upload zone and empty documents', async () => {
    api.listDocuments.mockResolvedValue([])
    renderPage(<Documents />)
    expect(screen.getByText('Drag & drop document here, or')).toBeInTheDocument()
    expect(await screen.findByText('No documents uploaded yet')).toBeInTheDocument()
  })

  it('renders list of documents with metadata', async () => {
    api.listDocuments.mockResolvedValue([
      {
        id: 'doc-1',
        original_filename: 'project_spec.pdf',
        file_size_bytes: 1048576,
        status: 'processed',
        chunk_count: 5,
        created_at: '2026-10-30T10:00:00Z',
      },
    ])
    renderPage(<Documents />)
    expect(await screen.findByText('project_spec.pdf')).toBeInTheDocument()
    expect(screen.getByText('1 MB')).toBeInTheDocument()
    expect(screen.getByText('5 chunks')).toBeInTheDocument()
  })
})

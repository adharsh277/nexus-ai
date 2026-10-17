import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { EmptyState, ErrorMessage, PageHeader, Spinner, formatDue, isOverdue } from '../components/ui.jsx'

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'completed', label: 'Completed' },
]

function AddTaskForm({ onCreated }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [due, setDue] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (!title.trim()) {
      setError(new Error('Title is required'))
      return
    }
    setSaving(true)
    setError(null)
    try {
      await api.createTask({
        title: title.trim(),
        description: description.trim() || null,
        due_date: due ? new Date(due).toISOString() : null,
      })
      setTitle('')
      setDescription('')
      setDue('')
      onCreated()
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="card mb-6 space-y-4" aria-label="Add task">
      <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
        <div>
          <label htmlFor="task-title" className="label">Title</label>
          <input id="task-title" className="input" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What needs doing?" />
        </div>
        <div>
          <label htmlFor="task-due" className="label">Due date</label>
          <input id="task-due" type="datetime-local" className="input" value={due} onChange={(e) => setDue(e.target.value)} />
        </div>
      </div>
      <div>
        <label htmlFor="task-description" className="label">Description (optional)</label>
        <textarea id="task-description" rows={2} className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <ErrorMessage error={error} />
      <button id="add-task-button" type="submit" className="btn-primary" disabled={saving}>
        {saving ? 'Adding…' : 'Add task'}
      </button>
    </form>
  )
}

function TaskRow({ task, onComplete, onDelete, busy }) {
  const done = task.status === 'completed'
  const overdue = isOverdue(task)
  return (
    <li className="animate-fade-in flex items-start gap-3 py-3">
      <button
        type="button"
        onClick={() => onComplete(task)}
        disabled={done || busy}
        aria-label={done ? `${task.title} is completed` : `Mark ${task.title} as complete`}
        className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border-2 transition ${
          done ? 'border-emerald-500 bg-emerald-500 text-white' : 'border-slate-400 hover:border-brand-400'
        }`}
      >
        {done && '✓'}
      </button>
      <div className="min-w-0 flex-1">
        <p className={`font-medium ${done ? 'text-slate-400 line-through' : ''}`}>{task.title}</p>
        {task.description && <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{task.description}</p>}
        {task.due_date && (
          <p className={`mt-1 text-xs ${overdue ? 'font-medium text-rose-500' : 'text-slate-500 dark:text-slate-400'}`}>
            {overdue ? 'Overdue · ' : 'Due '}
            {formatDue(task.due_date)}
          </p>
        )}
      </div>
      <button type="button" className="btn-ghost px-2 py-1 text-rose-500" onClick={() => onDelete(task)} disabled={busy} aria-label={`Delete ${task.title}`}>
        Delete
      </button>
    </li>
  )
}

export default function Tasks() {
  const [filter, setFilter] = useState('')
  const [tasks, setTasks] = useState(null)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setTasks(await api.listTasks({ status: filter || undefined }))
    } catch (e) {
      setError(e)
    }
  }, [filter])

  useEffect(() => {
    setTasks(null)
    load()
  }, [load])

  async function mutate(task, action) {
    setBusyId(task.id)
    setError(null)
    try {
      await action()
      await load()
    } catch (e) {
      setError(e)
    } finally {
      setBusyId(null)
    }
  }

  const handleComplete = (task) => mutate(task, () => api.completeTask(task.id))
  const handleDelete = (task) => {
    if (!window.confirm(`Delete "${task.title}"?`)) return
    // Optimistic removal; refetch afterwards keeps us in sync (and restores on error).
    setTasks((prev) => prev?.filter((t) => t.id !== task.id))
    mutate(task, () => api.deleteTask(task.id)).then(load)
  }

  return (
    <>
      <PageHeader title="Tasks" subtitle="Create, track and complete your tasks." />
      <AddTaskForm onCreated={load} />

      <section className="card">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Your tasks</h2>
          <div role="group" aria-label="Filter tasks" className="flex rounded-xl bg-slate-100 p-1 dark:bg-white/5">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                aria-pressed={filter === f.value}
                onClick={() => setFilter(f.value)}
                className={`rounded-lg px-3 py-1 text-sm transition ${
                  filter === f.value ? 'bg-white font-medium shadow-sm dark:bg-white/15' : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <ErrorMessage error={error} onRetry={load} />
        {tasks === null && !error && <Spinner label="Loading tasks…" />}
        {tasks && tasks.length === 0 && <EmptyState title="No tasks yet" hint="Add your first task above." />}
        {tasks && tasks.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-white/10">
            {tasks.map((t) => (
              <TaskRow key={t.id} task={t} busy={busyId === t.id} onComplete={handleComplete} onDelete={handleDelete} />
            ))}
          </ul>
        )}
      </section>
    </>
  )
}

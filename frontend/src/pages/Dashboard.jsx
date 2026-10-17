import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { EmptyState, ErrorMessage, PageHeader, Spinner, formatDue } from '../components/ui.jsx'

const STATS = [
  { key: 'pending', label: 'Pending', accent: 'from-brand-500/20 text-brand-600 dark:text-brand-300' },
  { key: 'completed', label: 'Completed', accent: 'from-emerald-500/20 text-emerald-600 dark:text-emerald-300' },
  { key: 'overdue', label: 'Overdue', accent: 'from-rose-500/20 text-rose-600 dark:text-rose-300' },
]

function TaskList({ title, tasks, empty }) {
  return (
    <section className="card animate-fade-in" aria-labelledby={`${title}-heading`}>
      <h2 id={`${title}-heading`} className="mb-4 font-semibold">{title}</h2>
      {tasks.length === 0 ? (
        <EmptyState title={empty} />
      ) : (
        <ul className="divide-y divide-slate-200 dark:divide-white/10">
          {tasks.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-3 py-2.5">
              <span className="truncate text-sm font-medium">{t.title}</span>
              <span className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{formatDue(t.due_date)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setData(await api.getDashboard())
    } catch (e) {
      setError(e)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Your day at a glance.">
        <Link to="/tasks" className="btn-primary">+ New task</Link>
      </PageHeader>

      <ErrorMessage error={error} onRetry={load} />
      {!data && !error && <Spinner />}

      {data && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            {STATS.map((s) => (
              <div key={s.key} className={`card animate-fade-in bg-linear-to-br ${s.accent} to-transparent`}>
                <p className="text-sm text-slate-500 dark:text-slate-400">{s.label}</p>
                <p className="mt-2 text-4xl font-semibold tabular-nums" data-testid={`stat-${s.key}`}>
                  {data.counts[s.key]}
                </p>
              </div>
            ))}
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <TaskList title="Due today" tasks={data.due_today} empty="Nothing due today 🎉" />
            <TaskList title="Upcoming" tasks={data.upcoming} empty="No upcoming tasks" />
          </div>
        </div>
      )}
    </>
  )
}

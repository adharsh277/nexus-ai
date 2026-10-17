export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-sm text-slate-500 dark:text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-400 border-t-transparent" />
      {label}
    </div>
  )
}

export function EmptyState({ title, hint }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center dark:border-white/10">
      <p className="font-medium">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  )
}

export function ErrorMessage({ error, onRetry }) {
  if (!error) return null
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
      <span>{error.message || String(error)}</span>
      {onRetry && (
        <button type="button" className="btn-ghost px-2 py-1" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function formatDue(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function isOverdue(task) {
  return task.status === 'pending' && task.due_date && new Date(task.due_date) < new Date()
}

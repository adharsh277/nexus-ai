import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { EmptyState, ErrorMessage, PageHeader, Spinner } from '../components/ui.jsx'

function formatDate(isoString) {
  if (!isoString) return '—'
  const d = new Date(isoString)
  return d.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function toLocalInputValues(isoString) {
  if (!isoString) return { date: '', time: '' }
  const d = new Date(isoString)
  const pad = (n) => String(n).padStart(2, '0')
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  return { date, time }
}

const STATUS_CONFIG = {
  pending: {
    label: 'Pending',
    badge: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
  },
  completed: {
    label: 'Completed',
    badge: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  },
  cancelled: {
    label: 'Cancelled',
    badge: 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/30',
  },
}

export default function Reminders() {
  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')

  // Create / Edit Modal State
  const [modalOpen, setModalOpen] = useState(false)
  const [editingReminder, setEditingReminder] = useState(null)
  const [formTitle, setFormTitle] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formDate, setFormDate] = useState('')
  const [formTime, setFormTime] = useState('')
  const [formTimezone, setFormTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC')
  const [formSaving, setFormSaving] = useState(false)
  const [formError, setFormError] = useState(null)

  // Delete Confirmation State
  const [deleteId, setDeleteId] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const loadReminders = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const filter = statusFilter === 'all' ? undefined : statusFilter
      const data = await api.listReminders({ status: filter, search: search.trim() || undefined })
      setReminders(data)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, search])

  useEffect(() => {
    loadReminders()
  }, [loadReminders])

  function openCreateModal() {
    setEditingReminder(null)
    setFormTitle('')
    setFormDescription('')
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    tomorrow.setHours(9, 0, 0, 0)
    const { date, time } = toLocalInputValues(tomorrow.toISOString())
    setFormDate(date)
    setFormTime(time)
    setFormTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC')
    setFormError(null)
    setModalOpen(true)
  }

  function openEditModal(reminder) {
    setEditingReminder(reminder)
    setFormTitle(reminder.title)
    setFormDescription(reminder.description || '')
    const { date, time } = toLocalInputValues(reminder.due_at)
    setFormDate(date)
    setFormTime(time)
    setFormTimezone(reminder.timezone || 'UTC')
    setFormError(null)
    setModalOpen(true)
  }

  async function handleSaveReminder(e) {
    e.preventDefault()
    if (!formTitle.trim()) {
      setFormError(new Error('Title is required'))
      return
    }
    if (!formDate || !formTime) {
      setFormError(new Error('Date and time are required'))
      return
    }

    setFormSaving(true)
    setFormError(null)

    try {
      const combinedDate = new Date(`${formDate}T${formTime}`)
      if (isNaN(combinedDate.getTime())) {
        throw new Error('Invalid date or time entered')
      }
      const isoDueAt = combinedDate.toISOString()

      if (editingReminder) {
        await api.updateReminder(editingReminder.id, {
          title: formTitle.trim(),
          description: formDescription.trim() || null,
          due_at: isoDueAt,
          timezone: formTimezone,
        })
      } else {
        await api.createReminder({
          title: formTitle.trim(),
          description: formDescription.trim() || null,
          due_at: isoDueAt,
          timezone: formTimezone,
        })
      }
      setModalOpen(false)
      await loadReminders()
    } catch (err) {
      setFormError(err)
    } finally {
      setFormSaving(false)
    }
  }

  async function handleComplete(id) {
    try {
      await api.completeReminder(id)
      await loadReminders()
    } catch (err) {
      setError(err)
    }
  }

  async function handleCancel(id) {
    try {
      await api.cancelReminder(id)
      await loadReminders()
    } catch (err) {
      setError(err)
    }
  }

  async function confirmDelete() {
    if (!deleteId) return
    setDeleting(true)
    try {
      await api.deleteReminder(deleteId)
      setDeleteId(null)
      await loadReminders()
    } catch (err) {
      setError(err)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Reminders"
        subtitle="Manage scheduled reminders with smart notifications and time awareness"
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadReminders}
            className="btn-ghost px-3 py-2 text-xs font-semibold"
            title="Refresh reminders"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <button
            id="create-reminder-btn"
            type="button"
            onClick={openCreateModal}
            className="btn-primary px-4 py-2 text-sm font-semibold cursor-pointer"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Reminder
          </button>
        </div>
      </PageHeader>

      <ErrorMessage error={error} onRetry={loadReminders} />

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Status Tabs */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 w-fit">
          {[
            { id: 'all', label: 'All' },
            { id: 'pending', label: 'Pending' },
            { id: 'completed', label: 'Completed' },
            { id: 'cancelled', label: 'Cancelled' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                statusFilter === tab.id
                  ? 'bg-white dark:bg-slate-900 text-brand-600 dark:text-brand-300 shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative max-w-xs w-full">
          <input
            type="text"
            className="input pr-8 py-2 text-xs"
            placeholder="Search reminders…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <Spinner label="Loading reminders…" />
      ) : reminders.length === 0 ? (
        <EmptyState
          title="No reminders found"
          hint={
            statusFilter !== 'all' || search
              ? 'Try adjusting your filters or search term.'
              : 'Create a new reminder to stay organized, or ask Nexus in Chat.'
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reminders.map((r) => {
            const statusCfg = STATUS_CONFIG[r.status] || STATUS_CONFIG.pending
            const isDueSoon =
              r.status === 'pending' &&
              new Date(r.due_at) < new Date(Date.now() + 24 * 60 * 60 * 1000)
            const isPast = r.status === 'pending' && new Date(r.due_at) < new Date()

            return (
              <div
                key={r.id}
                className="card flex flex-col justify-between hover:border-brand-500/40 transition group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${statusCfg.badge}`}
                    >
                      {statusCfg.label}
                    </span>
                    {isPast && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30">
                        Overdue
                      </span>
                    )}
                    {!isPast && isDueSoon && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                        Due Soon
                      </span>
                    )}
                  </div>

                  <h3 className="font-semibold text-base text-slate-900 dark:text-slate-100 mb-1 leading-snug">
                    {r.title}
                  </h3>

                  {r.description && (
                    <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 mb-3">
                      {r.description}
                    </p>
                  )}

                  <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 mt-2">
                    <svg className="h-4 w-4 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>{formatDate(r.due_at)}</span>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-white/5 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1">
                    {r.status === 'pending' && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleComplete(r.id)}
                          className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 transition cursor-pointer"
                          title="Mark complete"
                        >
                          ✓ Done
                        </button>
                        <button
                          type="button"
                          onClick={() => handleCancel(r.id)}
                          className="px-2 py-1 text-xs rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-white/10 transition cursor-pointer"
                          title="Cancel reminder"
                        >
                          Cancel
                        </button>
                      </>
                    )}
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => openEditModal(r)}
                      className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 transition cursor-pointer"
                      title="Edit reminder"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteId(r.id)}
                      className="p-1.5 text-slate-400 hover:text-rose-500 rounded-lg hover:bg-rose-500/10 transition cursor-pointer"
                      title="Delete reminder"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create / Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="card w-full max-w-lg shadow-xl border border-slate-200 dark:border-white/10 p-6 animate-fade-in">
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-4">
              {editingReminder ? 'Edit Reminder' : 'Create Reminder'}
            </h2>

            <ErrorMessage error={formError} />

            <form onSubmit={handleSaveReminder} className="space-y-4 mt-2">
              <div>
                <label htmlFor="rem-title" className="label">
                  Title *
                </label>
                <input
                  id="rem-title"
                  type="text"
                  required
                  maxLength={200}
                  className="input"
                  placeholder="e.g. Doctor appointment, Submit taxes"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="rem-desc" className="label">
                  Description
                </label>
                <textarea
                  id="rem-desc"
                  rows={2}
                  maxLength={5000}
                  className="input resize-none"
                  placeholder="Optional details or context"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="rem-date" className="label">
                    Date *
                  </label>
                  <input
                    id="rem-date"
                    type="date"
                    required
                    className="input"
                    value={formDate}
                    onChange={(e) => setFormDate(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="rem-time" className="label">
                    Time *
                  </label>
                  <input
                    id="rem-time"
                    type="time"
                    required
                    className="input"
                    value={formTime}
                    onChange={(e) => setFormTime(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="rem-tz" className="label">
                  Timezone
                </label>
                <input
                  id="rem-tz"
                  type="text"
                  className="input"
                  value={formTimezone}
                  onChange={(e) => setFormTimezone(e.target.value)}
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="btn-ghost px-4 py-2 text-sm"
                  disabled={formSaving}
                >
                  Cancel
                </button>
                <button
                  id="save-reminder-submit"
                  type="submit"
                  className="btn-primary px-5 py-2 text-sm font-semibold cursor-pointer"
                  disabled={formSaving}
                >
                  {formSaving ? 'Saving…' : editingReminder ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="card w-full max-w-md shadow-xl border border-slate-200 dark:border-white/10 p-6 animate-fade-in">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-2">
              Delete Reminder?
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
              This reminder will be permanently deleted. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteId(null)}
                className="btn-ghost px-4 py-2 text-sm"
                disabled={deleting}
              >
                Keep
              </button>
              <button
                id="confirm-delete-reminder-btn"
                type="button"
                onClick={confirmDelete}
                className="btn bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 text-sm font-semibold cursor-pointer"
                disabled={deleting}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

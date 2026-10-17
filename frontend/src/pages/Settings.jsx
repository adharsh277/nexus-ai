import { useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { PageHeader } from '../components/ui.jsx'

export default function Settings() {
  const [health, setHealth] = useState('checking…')

  useEffect(() => {
    api.health().then((h) => setHealth(`API ${h.status}, database ${h.database}`)).catch((e) => setHealth(e.message))
  }, [])

  return (
    <>
      <PageHeader title="Settings" subtitle="Preferences and integrations will live here." />
      <div className="card space-y-3 text-sm">
        <p>
          <span className="label inline">Account</span> Local default user (authentication arrives in a later phase).
        </p>
        <p>
          <span className="label inline">Status</span> <span data-testid="health">{health}</span>
        </p>
        <p className="text-slate-500 dark:text-slate-400">AI model, reminders and integrations: coming in Phase 2.</p>
      </div>
    </>
  )
}

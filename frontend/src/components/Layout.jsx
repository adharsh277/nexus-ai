import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import GalaxyLogo from './GalaxyLogo.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'M3 12l9-9 9 9M5 10v10h14V10' },
  { to: '/tasks', label: 'Tasks', icon: 'M9 11l3 3 8-8M4 12v7a1 1 0 001 1h14' },
  { to: '/chat', label: 'Chat', icon: 'M4 5h16v11H8l-4 4z' },
  { to: '/settings', label: 'Settings', icon: 'M12 15a3 3 0 100-6 3 3 0 000 6zM4 12h2m12 0h2M12 4v2m0 12v2' },
]

function Icon({ d }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  )
}

export default function Layout() {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 btn-primary">
        Skip to content
      </a>

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform border-r border-slate-200 bg-white/90 p-4 backdrop-blur transition-transform
          dark:border-white/10 dark:bg-slate-950/80 md:static md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="mb-8 flex items-center gap-3 px-2">
          <GalaxyLogo size={40} />
          <div>
            <p className="font-bold text-base leading-tight tracking-wide bg-gradient-to-r from-sky-400 via-indigo-200 to-fuchsia-400 bg-clip-text text-transparent">Nexus AI</p>
            <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">Cosmic Assistant</p>
          </div>
        </div>
        <nav aria-label="Main">
          <ul className="space-y-1">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition ${
                      isActive
                        ? 'bg-brand-500/15 text-brand-600 dark:text-brand-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/5'
                    }`
                  }
                >
                  <Icon d={item.icon} />
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <p className="absolute bottom-4 left-6 text-xs text-slate-400">Phase 1 · v0.1</p>
      </aside>

      {open && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setOpen(false)} aria-hidden="true" />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 px-4 py-3 dark:border-white/10 md:hidden">
          <button type="button" className="btn-ghost px-2" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}>
            <Icon d="M4 6h16M4 12h16M4 18h16" />
          </button>
          <div className="flex items-center gap-2">
            <GalaxyLogo size={28} />
            <span className="font-bold text-sm tracking-wide bg-gradient-to-r from-sky-400 via-indigo-200 to-fuchsia-400 bg-clip-text text-transparent">Nexus AI</span>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

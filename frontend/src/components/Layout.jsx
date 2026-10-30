import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import GalaxyLogo from './GalaxyLogo.jsx'
import NotificationBell from './NotificationBell.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'M3 12l9-9 9 9M5 10v10h14V10' },
  { to: '/tasks', label: 'Tasks', icon: 'M9 11l3 3 8-8M4 12v7a1 1 0 001 1h14' },
  { to: '/reminders', label: 'Reminders', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  { to: '/documents', label: 'My Documents', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()
  const isChat = location.pathname.startsWith('/chat')

  return (
    <div className={`flex relative ${isChat ? 'h-screen max-h-screen overflow-hidden' : 'min-h-screen'}`}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 btn-primary">
        Skip to content
      </a>

      {/* Floating expand button when sidebar is collapsed on desktop */}
      {sidebarCollapsed && (
        <button
          type="button"
          onClick={() => setSidebarCollapsed(false)}
          className="fixed top-3 left-3 z-30 hidden md:flex items-center gap-2 rounded-xl border border-slate-200/80 bg-white/90 px-3 py-2 text-xs font-semibold shadow-md backdrop-blur-md transition hover:bg-slate-100 dark:border-white/10 dark:bg-slate-900/90 dark:text-slate-200 dark:hover:bg-white/10 cursor-pointer"
          title="Show navigation sidebar"
          aria-label="Expand sidebar"
        >
          <Icon d="M4 6h16M4 12h16M4 18h16" />
          <span>Menu</span>
        </button>
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 shrink-0 transform border-r border-slate-200 bg-white/90 p-4 backdrop-blur transition-transform
          dark:border-white/10 dark:bg-slate-950/80 ${
            sidebarCollapsed ? 'md:hidden' : 'md:static md:translate-x-0'
          } ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="mb-8 flex items-center justify-between px-2">
          <div className="flex items-center gap-3">
            <GalaxyLogo size={38} />
            <div>
              <p className="font-bold text-base leading-tight tracking-wide bg-gradient-to-r from-sky-400 via-indigo-200 to-fuchsia-400 bg-clip-text text-transparent">Nexus AI</p>
              <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">Cosmic Assistant</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSidebarCollapsed(true)}
            className="hidden md:flex p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/10 transition cursor-pointer"
            title="Hide sidebar"
            aria-label="Collapse sidebar"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
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
                        ? 'bg-brand-500/15 text-brand-600 dark:text-brand-300 shadow-xs'
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
        <p className="absolute bottom-4 left-6 text-xs text-slate-400">Phase 2 · v0.2</p>
      </aside>

      {open && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setOpen(false)} aria-hidden="true" />}

      <div className="flex min-w-0 flex-1 flex-col h-full overflow-hidden">
        {/* Top Header with Notification Bell */}
        <header className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5 dark:border-white/10 bg-white/60 dark:bg-slate-950/40 backdrop-blur-md shrink-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="btn-ghost px-2 md:hidden"
              aria-label="Open navigation"
              aria-expanded={open}
              onClick={() => setOpen(true)}
            >
              <Icon d="M4 6h16M4 12h16M4 18h16" />
            </button>
            <div className="flex items-center gap-2 md:hidden">
              <GalaxyLogo size={28} />
              <span className="font-bold text-sm tracking-wide bg-gradient-to-r from-sky-400 via-indigo-200 to-fuchsia-400 bg-clip-text text-transparent">Nexus AI</span>
            </div>
            <div className="hidden md:flex items-center gap-2 text-xs text-slate-400">
              <span>Personal Automation & Document Assistant</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <NotificationBell />
          </div>
        </header>

        <main
          id="main"
          className={
            isChat
              ? 'w-full flex-1 flex flex-col min-h-0 h-full p-2 md:p-3 overflow-hidden'
              : 'mx-auto w-full max-w-6xl flex-1 p-4 md:p-8 overflow-y-auto'
          }
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}

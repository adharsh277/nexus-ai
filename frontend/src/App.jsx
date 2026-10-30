import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Chat from './pages/Chat.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Documents from './pages/Documents.jsx'
import Reminders from './pages/Reminders.jsx'
import Settings from './pages/Settings.jsx'
import Tasks from './pages/Tasks.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="reminders" element={<Reminders />} />
        <Route path="documents" element={<Documents />} />
        <Route path="chat" element={<Chat />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '') + '/api'

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message)
    this.status = status
    this.details = details
  }
}

async function request(path, { method = 'GET', body, params } = {}) {
  const url = new URL(BASE_URL + path)
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  })

  let res
  try {
    res = await fetch(url, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running?', 0)
  }

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const err = data?.error
    const detail = err?.details?.[0]
    const message = detail ? `${detail.loc.at(-1)}: ${detail.msg}` : err?.message || `Request failed (${res.status})`
    throw new ApiError(message, res.status, err?.details)
  }
  return data
}

export const api = {
  health: () => request('/health'),

  getDashboard: () =>
    request('/dashboard', { params: { tz_offset_minutes: -new Date().getTimezoneOffset() } }),

  listTasks: ({ status } = {}) => request('/tasks', { params: { status } }),
  createTask: (task) => request('/tasks', { method: 'POST', body: task }),
  updateTask: (id, changes) => request(`/tasks/${id}`, { method: 'PATCH', body: changes }),
  completeTask: (id) => request(`/tasks/${id}/complete`, { method: 'POST' }),
  deleteTask: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),

  listConversations: () => request('/conversations'),
  createConversation: (title) => request('/conversations', { method: 'POST', body: title ? { title } : {} }),
  listMessages: (conversationId) => request(`/conversations/${conversationId}/messages`),
  sendMessage: (conversationId, content) =>
    request(`/conversations/${conversationId}/messages`, { method: 'POST', body: { content } }),
}

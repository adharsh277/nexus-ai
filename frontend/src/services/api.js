const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '') + '/api'

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message)
    this.status = status
    this.details = details
  }
}

async function request(path, { method = 'GET', body, params, isFormData = false } = {}) {
  const url = new URL(BASE_URL + path)
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  })

  let res
  try {
    const headers = {}
    let reqBody = body
    if (body !== undefined && !isFormData && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
      reqBody = JSON.stringify(body)
    }
    res = await fetch(url, {
      method,
      headers: Object.keys(headers).length ? headers : undefined,
      body: reqBody,
    })
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running?', 0)
  }

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const err = data?.error || data?.detail
    let message = `Request failed (${res.status})`
    if (typeof err === 'string') {
      message = err
    } else if (err?.message) {
      message = err.message
    } else if (Array.isArray(err)) {
      message = err[0]?.msg ? `${err[0].loc?.at(-1) || 'field'}: ${err[0].msg}` : JSON.stringify(err[0])
    }
    throw new ApiError(message, res.status, data)
  }
  return data
}

export const api = {
  health: () => request('/health'),

  getDashboard: () =>
    request('/dashboard', { params: { tz_offset_minutes: -new Date().getTimezoneOffset() } }),

  // Tasks
  listTasks: ({ status } = {}) => request('/tasks', { params: { status } }),
  createTask: (task) => request('/tasks', { method: 'POST', body: task }),
  updateTask: (id, changes) => request(`/tasks/${id}`, { method: 'PATCH', body: changes }),
  completeTask: (id) => request(`/tasks/${id}/complete`, { method: 'POST' }),
  deleteTask: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),

  // Reminders
  listReminders: ({ status, search, sort = 'due_at' } = {}) =>
    request('/reminders', { params: { status, search, sort } }),
  getReminder: (id) => request(`/reminders/${id}`),
  createReminder: (reminder) => request('/reminders', { method: 'POST', body: reminder }),
  updateReminder: (id, changes) => request(`/reminders/${id}`, { method: 'PATCH', body: changes }),
  completeReminder: (id) => request(`/reminders/${id}/complete`, { method: 'POST' }),
  cancelReminder: (id) => request(`/reminders/${id}/cancel`, { method: 'POST' }),
  deleteReminder: (id) => request(`/reminders/${id}`, { method: 'DELETE' }),

  // Documents
  listDocuments: () => request('/documents'),
  getDocument: (id) => request(`/documents/${id}`),
  deleteDocument: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
  getDocumentChunks: (id) => request(`/documents/${id}/chunks`),
  triggerProcessDocument: (id) => request(`/documents/${id}/process`, { method: 'POST' }),
  searchDocuments: ({ query, top_k = 5, document_id = null }) =>
    request('/documents/search', { method: 'POST', body: { query, top_k, document_id } }),
  uploadDocument: (file, { background = false, onProgress } = {}) => {
    const formData = new FormData()
    formData.append('file', file)
    if (onProgress) {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', `${BASE_URL}/documents/upload?background=${background}`)
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            onProgress(Math.round((e.loaded / e.total) * 100))
          }
        }
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.responseText))
            } catch {
              resolve(null)
            }
          } else {
            let msg = `Upload failed (${xhr.status})`
            try {
              const res = JSON.parse(xhr.responseText)
              msg = res.detail || res.error?.message || msg
            } catch {}
            reject(new ApiError(msg, xhr.status))
          }
        }
        xhr.onerror = () => reject(new ApiError('Upload failed: network error', 0))
        xhr.send(formData)
      })
    }
    return request(`/documents/upload?background=${background}`, {
      method: 'POST',
      body: formData,
      isFormData: true,
    })
  },

  // Notifications
  listNotifications: ({ unread_only = false, limit = 50 } = {}) =>
    request('/notifications', { params: { unread_only, limit } }),
  getUnreadCount: () => request('/notifications/unread-count'),
  markNotificationRead: (id) => request(`/notifications/${id}/read`, { method: 'PATCH' }),
  markAllNotificationsRead: () => request('/notifications/mark-all-read', { method: 'POST' }),

  // Chat & Conversations
  listConversations: () => request('/conversations'),
  createConversation: (title) => request('/conversations', { method: 'POST', body: title ? { title } : {} }),
  deleteConversation: (conversationId) =>
    request(`/conversations/${conversationId}`, { method: 'DELETE' }),
  listMessages: (conversationId) => request(`/conversations/${conversationId}/messages`),
  sendMessage: (conversationId, content) =>
    request(`/conversations/${conversationId}/messages`, { method: 'POST', body: { content } }),
}

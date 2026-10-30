import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../services/api.js'
import { ErrorMessage, Spinner } from '../components/ui.jsx'
import GalaxyLogo from '../components/GalaxyLogo.jsx'

function sanitizeText(raw) {
  if (!raw) return ''
  let cleaned = raw
  cleaned = cleaned.replace(/<tool_code>[\s\S]*?<\/tool_code>/gi, '')
  cleaned = cleaned.replace(/<tool_call>[\s\S]*?<\/tool_call>/gi, '')
  cleaned = cleaned.replace(/<\/?untrusted_document_content[^>]*>/gi, '')
  cleaned = cleaned.replace(/<\/?untrusted_document_context[^>]*>/gi, '')
  cleaned = cleaned.replace(/default_api\.[a-zA-Z0-9_]+\([^)]*\)/gi, '')
  return cleaned.trim()
}

function RenderFormattedContent({ text, isUser }) {
  if (isUser) {
    return <span className="whitespace-pre-wrap">{text}</span>
  }

  const cleaned = sanitizeText(text)
  if (!cleaned) {
    return <span className="italic text-slate-400">Action processed.</span>
  }

  // Regex to detect citations: [Document: Filename, Page: X] or [Document: Filename]
  const citationRegex = /\[Document:\s*([^,\]]+)(?:,\s*Page:\s*([^\]]+))?\]/g
  const parts = []
  let lastIndex = 0
  let match

  while ((match = citationRegex.exec(cleaned)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: cleaned.substring(lastIndex, match.index) })
    }
    parts.push({
      type: 'citation',
      docName: match[1].trim(),
      page: match[2]?.trim(),
    })
    lastIndex = citationRegex.lastIndex
  }

  if (lastIndex < cleaned.length) {
    parts.push({ type: 'text', content: cleaned.substring(lastIndex) })
  }

  return (
    <div className="whitespace-pre-wrap leading-relaxed space-y-1">
      {parts.map((p, idx) => {
        if (p.type === 'citation') {
          return (
            <span
              key={idx}
              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 mx-1 rounded-lg text-xs font-semibold bg-brand-500/10 text-brand-600 dark:text-brand-300 border border-brand-500/25 shadow-xs align-baseline"
              title={`Source: ${p.docName}${p.page ? ` (Page ${p.page})` : ''}`}
            >
              <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="truncate max-w-[140px] sm:max-w-[200px]">{p.docName}</span>
              {p.page && <span className="text-[10px] opacity-75 font-mono">p.{p.page}</span>}
            </span>
          )
        }
        return <span key={idx}>{p.content}</span>
      })}
    </div>
  )
}

function Bubble({ message }) {
  const mine = message.role === 'user'
  return (
    <li className={`animate-fade-in flex gap-3 ${mine ? 'justify-end' : 'justify-start items-start'}`}>
      {!mine && (
        <div className="mt-1 shrink-0 rounded-full p-1 bg-brand-500/10 dark:bg-brand-500/20 shadow-xs">
          <GalaxyLogo size={26} />
        </div>
      )}
      <div
        className={`rounded-2xl text-sm md:text-base shadow-sm transition-all ${
          mine
            ? 'max-w-[85%] md:max-w-2xl rounded-br-xs bg-linear-to-r from-brand-500 via-indigo-500 to-cyan-500 px-5 py-3.5 text-white shadow-brand-500/15'
            : 'max-w-[92%] md:max-w-3xl rounded-bl-xs border border-slate-200/80 bg-white/95 dark:border-white/10 dark:bg-white/5 px-5 py-4 backdrop-blur-sm text-slate-800 dark:text-slate-100'
        }`}
      >
        <span className="sr-only">{mine ? 'You: ' : 'Assistant: '}</span>
        <RenderFormattedContent text={message.content} isUser={mine} />
      </div>
    </li>
  )
}

export default function Chat() {
  const [params, setParams] = useSearchParams()
  const activeId = params.get('c')
  const promptParam = params.get('prompt')
  const [conversations, setConversations] = useState(null)
  const [messages, setMessages] = useState([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const endRef = useRef(null)

  useEffect(() => {
    if (promptParam) {
      setInput(promptParam)
      // Clear the prompt query param while keeping conversation id
      setParams(activeId ? { c: activeId } : {}, { replace: true })
    }
  }, [promptParam, activeId, setParams])

  const loadConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations())
    } catch (e) {
      setError(e)
      setConversations([])
    }
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  useEffect(() => {
    if (!activeId) {
      setMessages([])
      return
    }
    let cancelled = false
    setLoadingMessages(true)
    setError(null)
    api
      .listMessages(activeId)
      .then((m) => !cancelled && setMessages(m))
      .catch((e) => !cancelled && setError(e))
      .finally(() => !cancelled && setLoadingMessages(false))
    return () => {
      cancelled = true
    }
  }, [activeId])

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, sending])

  const select = (id) => setParams(id ? { c: id } : {})

  async function newConversation() {
    setError(null)
    try {
      const conv = await api.createConversation()
      setConversations((prev) => [conv, ...(prev || [])])
      select(conv.id)
    } catch (e) {
      setError(e)
    }
  }

  async function deleteConversation(e, id) {
    e.stopPropagation()
    if (!window.confirm('Delete this conversation? This action cannot be undone.')) return
    try {
      await api.deleteConversation(id)
      setConversations((prev) => (prev ? prev.filter((c) => c.id !== id) : []))
      if (activeId === id) {
        select(null)
        setMessages([])
      }
    } catch (err) {
      setError(err)
    }
  }

  async function send(e) {
    e?.preventDefault()
    const content = input.trim()
    if (!content || sending) return

    setInput('')
    setError(null)

    const tempId = 'temp-' + Date.now()
    const optimisticUserMsg = {
      id: tempId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimisticUserMsg])
    setSending(true)

    try {
      let convId = activeId
      if (!convId) {
        const conv = await api.createConversation()
        convId = conv.id
        select(convId)
      }
      const { user_message, assistant_message } = await api.sendMessage(convId, content)
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempId && m.id !== user_message.id),
        user_message,
        assistant_message,
      ])
      loadConversations()
    } catch (err) {
      setError(err)
    } finally {
      setSending(false)
    }
  }

  const activeTitle = conversations?.find((c) => c.id === activeId)?.title

  return (
    <div className="flex h-full w-full gap-3 md:gap-4 min-h-0 overflow-hidden">
      {/* Conversations Sidebar */}
      <aside
        className="card flex w-72 md:w-80 shrink-0 min-h-0 flex-col p-3 shadow-md border border-slate-200 dark:border-white/10"
        aria-label="Conversations"
      >
        <button
          id="new-conversation-button"
          type="button"
          className="btn-primary mb-3 w-full py-2.5 flex items-center justify-center gap-2 text-sm font-semibold shadow-md cursor-pointer"
          onClick={newConversation}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          + New chat
        </button>

        {conversations === null ? (
          <Spinner />
        ) : conversations.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-slate-500 dark:text-slate-400">
            No previous conversations.
          </p>
        ) : (
          <ul className="min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1">
            {conversations.map((c) => {
              const selected = c.id === activeId
              return (
                <li key={c.id} className="group relative flex items-center">
                  <button
                    type="button"
                    onClick={() => select(c.id)}
                    aria-current={selected ? 'page' : undefined}
                    className={`w-full rounded-xl px-3.5 py-2.5 text-left text-sm transition flex items-center gap-2.5 pr-9 ${
                      selected
                        ? 'bg-brand-500/15 font-semibold text-brand-600 dark:text-brand-300 shadow-xs'
                        : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5'
                    }`}
                  >
                    <svg className="h-4 w-4 shrink-0 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    <span className="truncate">{c.title}</span>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => deleteConversation(e, c.id)}
                    className="absolute right-2 p-1.5 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 transition opacity-0 group-hover:opacity-100 focus:opacity-100 cursor-pointer"
                    title="Delete chat"
                    aria-label={`Delete ${c.title}`}
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </aside>

      {/* Main Message Thread */}
      <section
        className="card flex min-h-0 flex-1 flex-col p-0 shadow-lg border border-slate-200 dark:border-white/10 overflow-hidden"
        aria-label="Message thread"
      >
        {/* Chat Header Bar */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-3.5 dark:border-white/10 bg-white/40 dark:bg-slate-950/20 backdrop-blur-xs shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <h1 className="font-semibold text-sm md:text-base text-slate-800 dark:text-slate-100 truncate">
              {activeTitle || 'Chat'}
            </h1>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400 shrink-0">
            {activeId && (
              <button
                type="button"
                onClick={(e) => deleteConversation(e, activeId)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 transition cursor-pointer"
                title="Delete this chat"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                <span className="hidden sm:inline">Delete chat</span>
              </button>
            )}
            <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200 dark:border-white/10">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="hidden sm:inline">Online</span>
            </div>
          </div>
        </div>

        {/* Message Scroll Viewport */}
        <div className="min-h-0 flex-1 overflow-y-auto px-4 md:px-8 py-6" aria-live="polite">
          {loadingMessages ? (
            <div className="flex h-full items-center justify-center">
              <Spinner label="Loading messages…" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center max-w-lg mx-auto py-8">
              <div className="mb-4 p-4 rounded-3xl bg-brand-500/10 dark:bg-brand-500/20 shadow-inner">
                <GalaxyLogo size={52} />
              </div>
              <h2 className="text-xl md:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50 mb-2">
                Start a conversation
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-8 max-w-md">
                Ask Nexus to set reminders, search your documents, or manage tasks.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left">
                {[
                  { label: 'Set a reminder', prompt: 'Remind me to check project deliverables tomorrow at 10 AM' },
                  { label: 'List my reminders', prompt: 'What are my pending reminders?' },
                  { label: 'Ask documents', prompt: 'What do my uploaded documents say about the project scope?' },
                  { label: 'Task summary', prompt: 'List my pending tasks' },
                ].map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInput(item.prompt)
                    }}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-white/10 hover:border-brand-400 dark:hover:border-brand-400/50 hover:bg-slate-50 dark:hover:bg-white/5 text-left text-xs transition group cursor-pointer"
                  >
                    <div className="font-semibold text-slate-800 dark:text-slate-200 group-hover:text-brand-500 transition">
                      {item.label}
                    </div>
                    <div className="text-slate-500 dark:text-slate-400 truncate mt-0.5">
                      {item.prompt}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto w-full">
              <ul className="space-y-4">
                {messages.map((m) => (
                  <Bubble key={m.id} message={m} />
                ))}
              </ul>
            </div>
          )}

          {sending && (
            <div className="max-w-4xl mx-auto w-full mt-4 flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-2 rounded-2xl bg-brand-500/10 border border-brand-500/20 text-brand-600 dark:text-brand-300 text-xs font-medium shadow-xs">
                <span className="h-2 w-2 rounded-full bg-brand-500 animate-ping" />
                <span>Nexus is thinking and executing actions…</span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input Footer Bar */}
        <div className="border-t border-slate-200 p-4 dark:border-white/10 bg-white/60 dark:bg-slate-950/40 backdrop-blur-md shrink-0">
          <div className="max-w-4xl mx-auto w-full">
            <ErrorMessage error={error} />
            <form onSubmit={send} className="relative mt-1 flex items-center">
              <label htmlFor="chat-input" className="sr-only">
                Message
              </label>
              <input
                id="chat-input"
                className="input w-full pr-24 py-3.5 px-4 text-sm md:text-base rounded-2xl border-slate-300 dark:border-white/15 bg-white dark:bg-slate-900/90 shadow-md focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
                placeholder="Ask Nexus something or manage reminders…"
                maxLength={4000}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={sending}
              />
              <button
                id="send-message-button"
                type="submit"
                className="btn-primary absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 rounded-xl text-sm font-semibold shadow-sm transition cursor-pointer"
                disabled={sending || !input.trim()}
              >
                Send
              </button>
            </form>
            <p className="mt-2 text-center text-[11px] text-slate-400 dark:text-slate-500">
              Nexus AI Cosmic Assistant · Intelligent Conversations & Tool Orchestration
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

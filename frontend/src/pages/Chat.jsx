import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../services/api.js'
import { EmptyState, ErrorMessage, Spinner } from '../components/ui.jsx'
import GalaxyLogo from '../components/GalaxyLogo.jsx'

function Bubble({ message }) {
  const mine = message.role === 'user'
  return (
    <li className={`animate-fade-in flex gap-2.5 ${mine ? 'justify-end' : 'justify-start items-start'}`}>
      {!mine && (
        <div className="mt-0.5 shrink-0">
          <GalaxyLogo size={28} />
        </div>
      )}
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
          mine
            ? 'rounded-br-md bg-linear-to-r from-brand-500 to-cyan-500 text-white'
            : 'rounded-bl-md border border-slate-200 bg-white/90 dark:border-white/10 dark:bg-white/5 backdrop-blur-sm'
        }`}
      >
        <span className="sr-only">{mine ? 'You: ' : 'Assistant: '}</span>
        {message.content}
      </div>
    </li>
  )
}

export default function Chat() {
  const [params, setParams] = useSearchParams()
  const activeId = params.get('c')
  const [conversations, setConversations] = useState(null)
  const [messages, setMessages] = useState([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const endRef = useRef(null)

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

  async function send(e) {
    e.preventDefault()
    const content = input.trim()
    if (!content || sending) return
    setSending(true)
    setError(null)
    try {
      let convId = activeId
      if (!convId) {
        const conv = await api.createConversation()
        convId = conv.id
        select(convId)
      }
      const { user_message, assistant_message } = await api.sendMessage(convId, content)
      setMessages((prev) => [...prev, user_message, assistant_message])
      setInput('')
      loadConversations()
    } catch (err) {
      setError(err)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="grid h-[calc(100vh-8rem)] gap-4 md:grid-cols-[16rem_1fr]">
      <aside className="card flex min-h-0 flex-col p-3" aria-label="Conversations">
        <button id="new-conversation-button" type="button" className="btn-primary mb-3 w-full" onClick={newConversation}>
          + New chat
        </button>
        {conversations === null ? (
          <Spinner />
        ) : conversations.length === 0 ? (
          <p className="px-2 text-sm text-slate-500 dark:text-slate-400">No conversations yet.</p>
        ) : (
          <ul className="min-h-0 space-y-1 overflow-y-auto">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => select(c.id)}
                  aria-current={c.id === activeId ? 'page' : undefined}
                  className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm transition ${
                    c.id === activeId ? 'bg-brand-500/15 font-medium text-brand-600 dark:text-brand-300' : 'hover:bg-slate-100 dark:hover:bg-white/5'
                  }`}
                >
                  {c.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section className="card flex min-h-0 flex-col p-0" aria-label="Message thread">
        <h1 className="border-b border-slate-200 px-5 py-3 font-semibold dark:border-white/10">Chat</h1>
        <div className="min-h-0 flex-1 overflow-y-auto p-5" aria-live="polite">
          {loadingMessages ? (
            <Spinner label="Loading messages…" />
          ) : messages.length === 0 ? (
            <EmptyState title="Start a conversation" hint="Ask Nexus anything. Your conversation and context will be saved automatically." />
          ) : (
            <ul className="space-y-3">
              {messages.map((m) => (
                <Bubble key={m.id} message={m} />
              ))}
            </ul>
          )}
          {sending && <Spinner label="Nexus is thinking…" />}
          <div ref={endRef} />
        </div>
        <div className="border-t border-slate-200 p-3 dark:border-white/10">
          <ErrorMessage error={error} />
          <form onSubmit={send} className="mt-2 flex gap-2">
            <label htmlFor="chat-input" className="sr-only">Message</label>
            <input
              id="chat-input"
              className="input"
              placeholder="Ask Nexus something…"
              maxLength={4000}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={sending}
            />
            <button id="send-message-button" type="submit" className="btn-primary" disabled={sending || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      </section>
    </div>
  )
}

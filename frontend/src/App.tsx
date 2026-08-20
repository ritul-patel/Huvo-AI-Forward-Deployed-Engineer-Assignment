import { useState, useEffect, useRef, useCallback } from 'react'
import { sendMessage } from './api'
import type { Message } from './types'
import MessageBubble from './components/MessageBubble'
import TypingIndicator from './components/TypingIndicator'
import ChatInput from './components/ChatInput'
import AnalyticsPanel from './components/AnalyticsPanel'
import './App.css'

const WELCOME = "Hi! I'm the Northstar Homes AI assistant. I can help you explore Northstar One, understand your requirements, and arrange a site visit. What are you looking for?"

function makeId() {
  return Math.random().toString(36).slice(2)
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    { id: makeId(), role: 'assistant', content: WELCOME },
  ])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAnalytics, setShowAnalytics] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = useCallback(async (text: string) => {
    const userMsg: Message = { id: makeId(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setError(null)
    setLoading(true)

    try {
      const res = await sendMessage({ session_id: sessionId, message: text })
      if (!sessionId) setSessionId(res.session_id)
      setMessages(prev => [...prev, {
        id: makeId(),
        role: 'assistant',
        content: res.message,
        bookingStatus: res.booking_status ?? undefined,
      }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  function handleNewChat() {
    setMessages([{ id: makeId(), role: 'assistant', content: WELCOME }])
    setSessionId(null)
    setError(null)
  }

  const isStopped = false // will be set from analytics if needed — chat always stays open unless backend says stopped

  return (
    <div className={`app ${showAnalytics ? 'app--split' : ''}`}>

      {/* ── Header ──────────────────────────────────────────── */}
      <header className="header">
        <div className="header-brand">
          <span className="header-logo" aria-hidden="true">🏢</span>
          <div>
            <div className="header-title">Northstar Homes</div>
            <div className="header-subtitle">AI Sales Assistant · Northstar One, Sector 79</div>
          </div>
        </div>
        <div className="header-actions">
          <button
            className={`analytics-toggle-btn ${showAnalytics ? 'analytics-toggle-btn--active' : ''}`}
            onClick={() => setShowAnalytics(p => !p)}
            aria-pressed={showAnalytics}
            aria-label="Toggle analytics panel"
          >
            📊 Analytics
          </button>
          <button className="new-chat-btn" onClick={handleNewChat} aria-label="Start new conversation">
            + New Chat
          </button>
        </div>
      </header>

      {/* ── Main body: chat + optional analytics panel ──────── */}
      <div className="body-area">

        {/* Chat column */}
        <div className="chat-column">
          <main className="messages-area" aria-live="polite" aria-label="Conversation">
            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </main>

          {error && (
            <div className="error-banner" role="alert">
              ⚠ {error}
              <button className="error-dismiss" onClick={() => setError(null)} aria-label="Dismiss">×</button>
            </div>
          )}

          {isStopped ? (
            <div className="stopped-banner">
              Communication has been stopped as requested.
            </div>
          ) : (
            <ChatInput onSend={handleSend} disabled={loading} />
          )}
        </div>

        {/* Analytics panel column — only rendered when open */}
        {showAnalytics && (
          <aside className="analytics-column" aria-label="Lead analytics">
            <AnalyticsPanel sessionId={sessionId} />
          </aside>
        )}
      </div>
    </div>
  )
}


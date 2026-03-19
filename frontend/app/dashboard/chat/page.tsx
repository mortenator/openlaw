'use client'
export const dynamic = "force-dynamic"

import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import { Send, MessageSquare } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const SUGGESTION_CHIPS = [
  'Find companies expanding AI infrastructure',
  'Who should I reconnect with this week?',
  'Summarize recent signals from Microsoft',
  'What deals closed in my sector this month?',
]

export default function ChatPage() {
  const [token, setToken] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) setToken(session.access_token)
    })
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend(override?: string) {
    const msg = (override ?? input).trim()
    if (!msg || !token || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    setLoading(true)

    try {
      const { response } = await api.query.send(token, msg)
      setMessages((prev) => [...prev, { role: 'assistant', content: response }])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="mb-6">
        <h1
          style={{ color: 'var(--text-primary)' }}
          className="text-2xl font-semibold tracking-tight"
        >
          Ask OpenLaw
        </h1>
        <p style={{ color: 'var(--text-tertiary)' }} className="text-sm mt-1">
          Research prospects, find deal signals, analyze companies
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center mt-16 gap-6">
            <div
              style={{ background: 'var(--surface)', color: 'var(--text-tertiary)' }}
              className="w-12 h-12 rounded-xl flex items-center justify-center"
            >
              <MessageSquare size={24} />
            </div>
            <p style={{ color: 'var(--text-tertiary)' }} className="text-sm">
              Ask me anything — find target companies, research prospects, get market analysis...
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {SUGGESTION_CHIPS.map((chip) => (
                <button
                  key={chip}
                  onClick={() => handleSend(chip)}
                  style={{
                    background: 'var(--surface)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                  }}
                  className="px-3 py-2 rounded-lg text-xs hover:opacity-80 transition-opacity text-left"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              style={
                msg.role === 'user'
                  ? { background: 'var(--accent)', color: '#FFFFFF' }
                  : { background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-primary)' }
              }
              className={`max-w-xl px-4 py-3 rounded-2xl text-sm whitespace-pre-wrap ${
                msg.role === 'user' ? 'rounded-br-sm' : 'rounded-bl-sm'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
              className="rounded-2xl rounded-bl-sm px-4 py-3 text-sm"
            >
              <span className="animate-pulse">Thinking...</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        style={{ borderTop: '1px solid var(--border)' }}
        className="flex gap-3 pt-4"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Ask me anything..."
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
          }}
          className="flex-1 px-4 py-2.5 rounded-xl text-sm focus:outline-none focus:ring-2"
          disabled={loading}
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          style={{ background: 'var(--accent)' }}
          className="px-4 py-2.5 text-white rounded-xl hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
        >
          <Send size={16} />
          <span className="text-sm font-medium">Send</span>
        </button>
      </div>
    </div>
  )
}

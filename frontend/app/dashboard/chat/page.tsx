'use client'
export const dynamic = "force-dynamic"

import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Send, MessageSquare } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
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

    // Add empty assistant message that will be filled by stream
    setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true }])

    try {
      const res = await fetch(`${BASE_URL}/query/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: msg }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const data = line.slice(6).trim()
            if (data === '[DONE]') break
            try {
              const parsed = JSON.parse(data)
              if (parsed.token) {
                accumulated += parsed.token
                setMessages((prev) => {
                  const next = [...prev]
                  next[next.length - 1] = {
                    role: 'assistant',
                    content: accumulated,
                    streaming: true,
                  }
                  return next
                })
                bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
              }
              if (parsed.error) throw new Error(parsed.error)
            } catch {
              // skip malformed lines
            }
          }
        }
      }

      // Mark streaming done
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = { role: 'assistant', content: accumulated, streaming: false }
        return next
      })
    } catch {
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = {
          role: 'assistant',
          content: 'Sorry, something went wrong. Please try again.',
          streaming: false,
        }
        return next
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="mb-6">
        <h1 style={{ color: 'var(--text-primary)' }} className="text-2xl font-semibold tracking-tight">
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
                  className="px-3 py-2 rounded-lg text-xs hover:opacity-80 transition-opacity text-left cursor-pointer"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              <div
                style={{ background: 'var(--accent)', color: '#FFFFFF' }}
                className="max-w-xl px-4 py-3 rounded-2xl rounded-br-sm text-sm whitespace-pre-wrap"
              >
                {msg.content}
              </div>
            ) : (
              <div
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                }}
                className="max-w-2xl px-5 py-4 rounded-2xl rounded-bl-sm text-sm"
              >
                {msg.content ? (
                  <div className="prose-sm prose-headings:font-semibold prose-headings:tracking-tight prose-p:leading-relaxed prose-li:leading-relaxed prose-table:text-xs">
                    <ReactMarkdown
                      components={{
                        h1: ({ children }) => (
                          <h1 style={{ color: 'var(--text-primary)' }} className="text-base font-semibold mb-2 mt-4 first:mt-0">{children}</h1>
                        ),
                        h2: ({ children }) => (
                          <h2 style={{ color: 'var(--text-primary)' }} className="text-sm font-semibold mb-2 mt-4 first:mt-0">{children}</h2>
                        ),
                        h3: ({ children }) => (
                          <h3 style={{ color: 'var(--text-secondary)' }} className="text-xs font-semibold uppercase tracking-wider mb-2 mt-3 first:mt-0">{children}</h3>
                        ),
                        p: ({ children }) => (
                          <p style={{ color: 'var(--text-primary)' }} className="mb-2 last:mb-0 leading-relaxed">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul style={{ color: 'var(--text-primary)' }} className="list-disc list-inside mb-2 space-y-1">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol style={{ color: 'var(--text-primary)' }} className="list-decimal list-inside mb-2 space-y-1">{children}</ol>
                        ),
                        li: ({ children }) => (
                          <li style={{ color: 'var(--text-primary)' }} className="leading-relaxed">{children}</li>
                        ),
                        strong: ({ children }) => (
                          <strong style={{ color: 'var(--text-primary)' }} className="font-semibold">{children}</strong>
                        ),
                        em: ({ children }) => (
                          <em style={{ color: 'var(--text-secondary)' }} className="italic">{children}</em>
                        ),
                        code: ({ children }) => (
                          <code style={{ background: 'var(--surface)', color: 'var(--text-primary)' }} className="px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>
                        ),
                        blockquote: ({ children }) => (
                          <blockquote style={{ borderLeftColor: 'var(--accent)', color: 'var(--text-secondary)' }} className="border-l-2 pl-3 my-2 italic">{children}</blockquote>
                        ),
                        table: ({ children }) => (
                          <div className="overflow-x-auto mb-3">
                            <table style={{ borderColor: 'var(--border)' }} className="w-full text-xs border-collapse">{children}</table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead style={{ background: 'var(--surface)' }}>{children}</thead>
                        ),
                        th: ({ children }) => (
                          <th style={{ color: 'var(--text-tertiary)', borderColor: 'var(--border)' }} className="px-3 py-2 text-left font-medium uppercase tracking-wider border-b">{children}</th>
                        ),
                        td: ({ children }) => (
                          <td style={{ color: 'var(--text-primary)', borderColor: 'var(--border-subtle)' }} className="px-3 py-2 border-b">{children}</td>
                        ),
                        hr: () => (
                          <hr style={{ borderColor: 'var(--border)' }} className="my-3" />
                        ),
                        a: ({ href, children }) => (
                          <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-text)' }} className="hover:underline">{children}</a>
                        ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <span className="animate-pulse" style={{ color: 'var(--text-tertiary)' }}>●●●</span>
                )}
                {msg.streaming && msg.content && (
                  <span className="inline-block w-0.5 h-4 ml-0.5 align-middle animate-pulse" style={{ background: 'var(--accent)' }} />
                )}
              </div>
            )}
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ borderTop: '1px solid var(--border)' }} className="flex gap-3 pt-4">
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
          className="px-4 py-2.5 text-white rounded-xl hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2 cursor-pointer"
        >
          <Send size={16} />
          <span className="text-sm font-medium">Send</span>
        </button>
      </div>
    </div>
  )
}

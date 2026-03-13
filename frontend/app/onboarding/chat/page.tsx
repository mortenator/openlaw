'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'

type MessageRole = 'agent' | 'user'
interface ChatMessage {
  role: MessageRole
  content: string
}

type Phase = 'opening' | 'letsgo' | 'qa'

function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="bg-[#1B3A5C] rounded-full w-8 h-8 flex items-center justify-center text-xs flex-shrink-0 mt-1">
        ⚡
      </div>
      <div className="bg-white/5 border border-white/10 rounded-2xl px-4 py-3 flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-white/40 animate-bounce"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  )
}

function AgentMessage({ content }: { content: string }) {
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="bg-[#1B3A5C] rounded-full w-8 h-8 flex items-center justify-center text-xs flex-shrink-0 mt-1">
        ⚡
      </div>
      <div className="bg-white/5 border border-white/10 rounded-2xl p-4 max-w-lg text-sm text-white/90 leading-relaxed">
        {content}
      </div>
    </div>
  )
}

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end mb-4">
      <div className="bg-[#1B3A5C] text-white rounded-2xl p-3 max-w-xs text-sm leading-relaxed">
        {content}
      </div>
    </div>
  )
}

function ChipSelect({
  options,
  onSubmit,
}: {
  options: string[]
  onSubmit: (selected: string[]) => void
}) {
  const [selected, setSelected] = useState<string[]>([])

  function toggle(opt: string) {
    setSelected((prev) =>
      prev.includes(opt) ? prev.filter((o) => o !== opt) : [...prev, opt]
    )
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => toggle(opt)}
            className={`rounded-full px-3 py-1.5 text-sm cursor-pointer transition-colors ${
              selected.includes(opt)
                ? 'border border-[#7B9FC4] bg-[#1B3A5C]/40 text-white'
                : 'border border-white/20 text-white/70 hover:border-white/40'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
      {selected.length > 0 && (
        <button
          onClick={() => onSubmit(selected)}
          className="bg-[#1B3A5C] text-white px-4 py-2 rounded-lg text-sm hover:opacity-90 transition-opacity"
        >
          Submit
        </button>
      )}
    </div>
  )
}

function FreeInput({
  onSubmit,
  placeholder = 'Type your answer…',
}: {
  onSubmit: (value: string) => void
  placeholder?: string
}) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim()) onSubmit(value.trim())
    }
  }

  function handleSend() {
    if (value.trim()) onSubmit(value.trim())
  }

  return (
    <div className="flex gap-2">
      <textarea
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder={placeholder}
        className="flex-1 bg-transparent border border-white/20 rounded-lg px-4 py-3 text-white placeholder-white/30 text-sm resize-none focus:outline-none focus:border-white/40"
      />
      <button
        onClick={handleSend}
        disabled={!value.trim()}
        className="bg-[#1B3A5C] text-white px-4 py-3 rounded-lg text-sm disabled:opacity-40 hover:opacity-90 transition-opacity flex-shrink-0"
      >
        Send
      </button>
    </div>
  )
}

const DONE_PHRASES = ['done', "that's good", "that's it", 'no more', 'nothing else', 'nope', 'no']
function isDone(str: string) {
  return DONE_PHRASES.some((p) => str.toLowerCase().trim() === p)
}

export default function OnboardingChatPage() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [firstName, setFirstName] = useState('')
  const [phase, setPhase] = useState<Phase>('opening')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [currentQ, setCurrentQ] = useState(0)
  const [inputType, setInputType] = useState<'chips' | 'free'>('free')
  const [chipOptions, setChipOptions] = useState<string[]>([])
  const [step3FollowUp, setStep3FollowUp] = useState(false)
  const [step3Companies, setStep3Companies] = useState('')
  const [qaKey, setQaKey] = useState(0) // reset input components
  const [bgMounted, setBgMounted] = useState(false)
  const [openingDone, setOpeningDone] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  // Load token + first name
  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      try {
        const status = await api.onboarding.status(t)
        const name = (status.answers.first_name as string) || ''
        setFirstName(name)
      } catch {
        // continue without name
      }
    })
  }, [])

  // Opening sequence — runs once token is loaded
  useEffect(() => {
    if (!token || openingDone) return
    setOpeningDone(true)

    const timeouts: ReturnType<typeof setTimeout>[] = []

    // Trigger bg transition
    const t0 = setTimeout(() => setBgMounted(true), 50)
    timeouts.push(t0)

    // Typing → message 1
    setIsTyping(true)
    const t1 = setTimeout(() => {
      setIsTyping(false)
      setMessages([
        {
          role: 'agent',
          content: `Hi ${firstName || 'there'}. I'm your OpenLaw agent — no name yet, fresh out of the box. 🌱`,
        },
      ])

      // Pause 600ms → typing → message 2
      const t2 = setTimeout(() => {
        setIsTyping(true)
        const t3 = setTimeout(() => {
          setIsTyping(false)
          setMessages((prev) => [
            ...prev,
            {
              role: 'agent',
              content:
                "I'll be your BD radar: tracking relationships, surfacing signals, drafting outreach when the timing is right.",
            },
          ])

          // Pause 400ms → typing → message 3 → show Let's go
          const t4 = setTimeout(() => {
            setIsTyping(true)
            const t5 = setTimeout(() => {
              setIsTyping(false)
              setMessages((prev) => [
                ...prev,
                {
                  role: 'agent',
                  content:
                    "Let's take 3 minutes. I'll ask a few questions, you answer however feels natural.",
                },
              ])
              setPhase('letsgo')
            }, 800)
            timeouts.push(t5)
          }, 400)
          timeouts.push(t4)
        }, 800)
        timeouts.push(t3)
      }, 600)
      timeouts.push(t2)
    }, 800)
    timeouts.push(t1)

    return () => {
      timeouts.forEach(clearTimeout)
    }
  }, [token, firstName, openingDone])

  function addMessage(msg: ChatMessage) {
    setMessages((prev) => [...prev, msg])
  }

  async function handleLetsGo() {
    if (!token) return
    setPhase('qa')
    setIsTyping(true)
    try {
      const res = await api.onboarding.chat(token, 1, null)
      setIsTyping(false)
      addMessage({ role: 'agent', content: res.agent_message })
      setCurrentQ(1)
      setInputType(res.input_type === 'chips' ? 'chips' : 'free')
      setChipOptions(res.options || [])
      setQaKey((k) => k + 1)
    } catch {
      setIsTyping(false)
      addMessage({ role: 'agent', content: 'Something went wrong. Please refresh and try again.' })
    }
  }

  async function handleAnswer(answer: string | string[]) {
    if (!token) return
    const answerStr = Array.isArray(answer) ? answer.join(', ') : answer
    addMessage({ role: 'user', content: answerStr })
    setQaKey((k) => k + 1)

    // Step 3 follow-up: show "Got it, watching..." then let them add more
    if (currentQ === 3 && !step3FollowUp) {
      setStep3Companies(answerStr)
      setIsTyping(true)
      setTimeout(() => {
        setIsTyping(false)
        addMessage({
          role: 'agent',
          content: `Got it — watching ${answerStr}. I'll flag anything relevant: GC hires, deal announcements, capital movements. Anything else to add? (or say done)`,
        })
        setStep3FollowUp(true)
        setInputType('free')
        setQaKey((k) => k + 1)
      }, 600)
      return
    }

    // Resolve step 3 follow-up: combine and call step 4
    if (step3FollowUp) {
      const finalCompanies = isDone(answerStr)
        ? step3Companies
        : `${step3Companies}, ${answerStr}`
      setStep3FollowUp(false)
      setIsTyping(true)
      try {
        const res = await api.onboarding.chat(token, 4, finalCompanies)
        setIsTyping(false)
        addMessage({ role: 'agent', content: res.agent_message })
        setCurrentQ(4)
        setInputType(res.input_type === 'chips' ? 'chips' : 'free')
        setChipOptions(res.options || [])
        setQaKey((k) => k + 1)
      } catch {
        setIsTyping(false)
        addMessage({ role: 'agent', content: 'Something went wrong. Please try again.' })
      }
      return
    }

    // Final question answered — save and navigate
    if (currentQ === 6) {
      setIsTyping(true)
      try {
        await api.onboarding.chat(token, 7, answerStr)
      } catch {
        // best-effort save
      }
      router.push('/onboarding/confirm')
      return
    }

    // Normal flow: call next step
    setIsTyping(true)
    try {
      const nextStep = currentQ + 1
      const res = await api.onboarding.chat(token, nextStep, answerStr)
      setIsTyping(false)
      addMessage({ role: 'agent', content: res.agent_message })
      setCurrentQ(nextStep)
      setInputType(res.input_type === 'chips' ? 'chips' : 'free')
      setChipOptions(res.options || [])
      setQaKey((k) => k + 1)
    } catch {
      setIsTyping(false)
      addMessage({ role: 'agent', content: 'Something went wrong. Please try again.' })
    }
  }

  const showInput = phase === 'qa' && !isTyping && currentQ > 0

  return (
    <div
      className="min-h-screen transition-colors"
      style={{
        backgroundColor: bgMounted ? '#0D0D0D' : '#F8F7F5',
        transitionDuration: '400ms',
      }}
    >
      <div className="max-w-2xl mx-auto pt-16 pb-32 px-4">
        {/* Messages */}
        {messages.map((msg, i) =>
          msg.role === 'agent' ? (
            <AgentMessage key={i} content={msg.content} />
          ) : (
            <UserMessage key={i} content={msg.content} />
          )
        )}

        {/* Typing indicator */}
        {isTyping && <TypingIndicator />}

        {/* Let's go button */}
        {phase === 'letsgo' && !isTyping && (
          <div className="flex justify-center mt-6">
            <button
              onClick={handleLetsGo}
              className="bg-[#1B3A5C] text-white px-8 py-3 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
            >
              Let&apos;s go →
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Fixed input area */}
      {showInput && (
        <div className="fixed bottom-0 left-0 right-0 bg-[#111] border-t border-white/10 p-4">
          <div className="max-w-2xl mx-auto">
            {inputType === 'chips' && chipOptions.length > 0 ? (
              <ChipSelect key={qaKey} options={chipOptions} onSubmit={handleAnswer} />
            ) : (
              <FreeInput
                key={qaKey}
                onSubmit={handleAnswer}
                placeholder={
                  step3FollowUp
                    ? 'Add more companies, or type "done"…'
                    : 'Type your answer…'
                }
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

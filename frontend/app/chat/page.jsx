'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { sendMessageApi, getConversationsApi, getConversationApi } from '@/lib/api'

const AREAS_LABELS = {
  penal: 'Penal', civil: 'Civil', laboral: 'Laboral',
  transito: 'Tránsito', comercial: 'Comercial',
  administrativo: 'Administrativo', constitucional: 'Constitucional', tributario: 'Tributario'
}

const AREA_COLORS = {
  penal: 'bg-red-100 text-red-700', civil: 'bg-blue-100 text-blue-700',
  laboral: 'bg-green-100 text-green-700', transito: 'bg-yellow-100 text-yellow-700',
  comercial: 'bg-purple-100 text-purple-700', administrativo: 'bg-orange-100 text-orange-700',
  constitucional: 'bg-pink-100 text-pink-700', tributario: 'bg-indigo-100 text-indigo-700',
}

export default function ChatPage() {
  const router = useRouter()
  const [user, setUser] = useState(null)
  const [conversations, setConversations] = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [lastMeta, setLastMeta] = useState(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Auth check
  useEffect(() => {
    const token = localStorage.getItem('lexia_token')
    const u = localStorage.getItem('lexia_user')
    if (!token) { router.push('/login'); return }
    if (u) setUser(JSON.parse(u))
    loadConversations()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function loadConversations() {
    try {
      const convs = await getConversationsApi()
      setConversations(convs)
    } catch {}
  }

  async function openConversation(id) {
    try {
      const conv = await getConversationApi(id)
      if (!conv) return
      setActiveConvId(id)
      setMessages(conv.messages.map(m => ({
        id: m.id, role: m.role, content: m.content,
        metadata: m.agent_metadata, created_at: m.created_at
      })))
      setLastMeta(null)
    } catch {}
  }

  function newChat() {
    setActiveConvId(null)
    setMessages([])
    setLastMeta(null)
    inputRef.current?.focus()
  }

  function logout() {
    localStorage.removeItem('lexia_token')
    localStorage.removeItem('lexia_user')
    router.push('/login')
  }

  async function sendMessage(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    const userMsg = { id: Date.now(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const data = await sendMessageApi(text, activeConvId)
      setActiveConvId(data.conversation_id)
      const assistantMsg = {
        id: data.message.id,
        role: 'assistant',
        content: data.message.content,
        areas: data.detected_areas,
        complexity: data.complexity,
        lawyers: data.suggested_lawyers,
        processes: data.suggested_processes,
      }
      setMessages(prev => [...prev, assistantMsg])
      setLastMeta({
        areas: data.detected_areas,
        complexity: data.complexity,
        lawyers: data.suggested_lawyers,
        processes: data.suggested_processes,
      })
      await loadConversations()
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1, role: 'error',
        content: err.message || 'Error al procesar tu consulta.'
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const complexityColors = {
    simple: 'text-green-600 bg-green-50',
    moderate: 'text-yellow-600 bg-yellow-50',
    complex: 'text-red-600 bg-red-50',
  }

  return (
    <div className="flex h-screen bg-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-200 flex-shrink-0 bg-lexia-900 text-white flex flex-col overflow-hidden`}>
        <div className="p-4 border-b border-lexia-700 flex items-center gap-2">
          <span className="text-xl">⚖</span>
          <span className="font-bold text-lg">Lexia</span>
        </div>

        <div className="p-3">
          <button onClick={newChat}
            className="w-full flex items-center gap-2 bg-lexia-500 hover:bg-lexia-600 text-white text-sm font-medium px-3 py-2.5 rounded-lg transition-colors">
            <span className="text-lg">+</span> Nueva consulta
          </button>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin px-3 pb-3 space-y-1">
          <p className="text-xs text-lexia-300 uppercase tracking-wide px-2 pb-1">Historial</p>
          {conversations.length === 0 && (
            <p className="text-xs text-lexia-400 px-2">Sin conversaciones aún</p>
          )}
          {conversations.map(conv => (
            <button key={conv.id} onClick={() => openConversation(conv.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors truncate ${
                activeConvId === conv.id ? 'bg-lexia-600' : 'hover:bg-lexia-800'
              }`}>
              <p className="truncate font-medium">{conv.title || 'Consulta sin título'}</p>
              <p className="text-lexia-400 text-[10px] mt-0.5">{conv.status}</p>
            </button>
          ))}
        </div>

        {/* User info */}
        <div className="p-3 border-t border-lexia-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-lexia-500 flex items-center justify-center text-sm font-bold">
              {user?.username?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.username || 'Invitado'}</p>
              {user?.is_guest && <p className="text-xs text-lexia-400">Modo invitado</p>}
            </div>
            <button onClick={logout} className="text-lexia-400 hover:text-white text-xs" title="Cerrar sesión">✕</button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3">
          <button onClick={() => setSidebarOpen(o => !o)}
            className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
            <div className="space-y-1">
              <div className="w-5 h-0.5 bg-slate-600" />
              <div className="w-5 h-0.5 bg-slate-600" />
              <div className="w-5 h-0.5 bg-slate-600" />
            </div>
          </button>
          <div>
            <h1 className="font-semibold text-slate-800">Consulta Legal</h1>
            <p className="text-xs text-slate-500">Legislación boliviana • Powered by IA local</p>
          </div>

          {lastMeta?.areas?.length > 0 && (
            <div className="ml-auto flex items-center gap-1.5 flex-wrap">
              {lastMeta.areas.map(a => (
                <span key={a} className={`text-xs px-2 py-0.5 rounded-full font-medium ${AREA_COLORS[a] || 'bg-slate-100 text-slate-600'}`}>
                  {AREAS_LABELS[a] || a}
                </span>
              ))}
              {lastMeta.complexity && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${complexityColors[lastMeta.complexity] || 'bg-slate-100 text-slate-600'}`}>
                  {lastMeta.complexity}
                </span>
              )}
            </div>
          )}
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <div className="text-6xl mb-4">⚖️</div>
              <h2 className="text-xl font-bold text-slate-700 mb-2">Bienvenido a Lexia</h2>
              <p className="text-slate-500 max-w-md text-sm leading-relaxed">
                Soy tu asistente legal especializado en legislación boliviana. Puedo orientarte sobre temas penales, laborales, civiles, tránsito y más.
              </p>
              <div className="mt-6 grid grid-cols-1 gap-2 w-full max-w-sm">
                {[
                  'Me despidieron sin causa justificada',
                  'Tuve un accidente de tránsito',
                  'Mi arrendatario no paga el alquiler',
                  'Me deben salarios de varios meses',
                ].map(q => (
                  <button key={q} onClick={() => { setInput(q); inputRef.current?.focus() }}
                    className="text-left text-sm bg-white border border-slate-200 hover:border-lexia-400 hover:bg-lexia-50 rounded-xl px-4 py-2.5 transition-colors text-slate-600">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role !== 'user' && (
                <div className="w-8 h-8 rounded-full bg-lexia-500 flex items-center justify-center text-white text-sm mr-2 mt-1 flex-shrink-0">
                  ⚖
                </div>
              )}
              <div className={`max-w-[75%] ${msg.role === 'user' ? 'max-w-[60%]' : ''}`}>
                <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-lexia-500 text-white rounded-tr-sm'
                    : msg.role === 'error'
                    ? 'bg-red-50 text-red-600 border border-red-200'
                    : 'bg-white text-slate-800 shadow-sm border border-slate-100 rounded-tl-sm'
                }`}>
                  {msg.content}
                </div>

                {/* Procesos sugeridos */}
                {msg.processes?.length > 0 && (
                  <div className="mt-2 space-y-2">
                    {msg.processes.map((p, i) => (
                      <div key={i} className="bg-blue-50 border border-blue-200 rounded-xl px-3 py-2.5 text-xs">
                        <p className="font-semibold text-blue-700">📋 {p.nombre}</p>
                        <p className="text-blue-600 mt-0.5">{p.institucion}</p>
                        {p.pasos && <p className="text-slate-600 mt-1">{p.pasos}</p>}
                      </div>
                    ))}
                  </div>
                )}

                {/* Abogados sugeridos */}
                {msg.lawyers?.length > 0 && (
                  <div className="mt-2 space-y-2">
                    <p className="text-xs text-slate-500 font-medium px-1">Abogados recomendados:</p>
                    {msg.lawyers.slice(0, 3).map((l, i) => (
                      <div key={i} className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5 text-xs">
                        <p className="font-semibold text-amber-700">👤 {l.nombre}</p>
                        <p className="text-slate-600">{l.ciudad} • {l.especialidades}</p>
                        {l.experiencia && <p className="text-slate-500 mt-0.5">{l.experiencia} años de experiencia</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="w-8 h-8 rounded-full bg-lexia-500 flex items-center justify-center text-white text-sm mr-2 flex-shrink-0">⚖</div>
              <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-slate-100">
                <div className="flex gap-1.5 items-center">
                  <div className="w-2 h-2 bg-lexia-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-lexia-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-lexia-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t border-slate-200 p-4">
          {user?.is_guest && (
            <div className="mb-2 text-center text-xs text-slate-500">
              Modo invitado — consultas limitadas •{' '}
              <a href="/register" className="text-lexia-500 hover:underline">Regístrate gratis para acceso ilimitado</a>
            </div>
          )}
          <form onSubmit={sendMessage} className="flex gap-2">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Describe tu situación legal..."
              className="flex-1 border border-slate-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-lexia-500 focus:border-transparent bg-slate-50"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="bg-lexia-500 hover:bg-lexia-600 disabled:opacity-40 text-white px-5 py-2.5 rounded-xl font-medium text-sm transition-colors flex items-center gap-1.5"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>Enviar <span>→</span></>
              )}
            </button>
          </form>
          <p className="text-center text-xs text-slate-400 mt-2">
            Lexia orienta pero no reemplaza a un abogado profesional
          </p>
        </div>
      </div>
    </div>
  )
}

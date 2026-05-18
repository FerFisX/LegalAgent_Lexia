const BASE = 'http://localhost:8000'

function getToken() {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('lexia_token')
}

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function loginApi(email, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Error al iniciar sesión')
  }
  return res.json()
}

export async function signupApi(email, username, password) {
  const res = await fetch(`${BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, username, password }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Error al registrarse')
  }
  return res.json()
}

export async function guestApi() {
  const res = await fetch(`${BASE}/auth/guest`, { method: 'POST' })
  if (!res.ok) throw new Error('Error al crear sesión de invitado')
  return res.json()
}

export async function getMeApi() {
  const res = await fetch(`${BASE}/auth/me`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
  })
  if (!res.ok) return null
  return res.json()
}

export async function sendMessageApi(message, conversationId = null) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Error al enviar mensaje')
  }
  return res.json()
}

export async function getConversationsApi() {
  const res = await fetch(`${BASE}/chat/conversations`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
  })
  if (!res.ok) return []
  return res.json()
}

export async function getConversationApi(id) {
  const res = await fetch(`${BASE}/chat/${id}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
  })
  if (!res.ok) return null
  return res.json()
}

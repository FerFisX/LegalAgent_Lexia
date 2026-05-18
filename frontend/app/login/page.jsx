'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { loginApi, guestApi } from '@/lib/api'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await loginApi(email, password)
      localStorage.setItem('lexia_token', data.access_token)
      localStorage.setItem('lexia_user', JSON.stringify({ id: data.user_id, username: data.username, is_guest: false }))
      router.push('/chat')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleGuest() {
    setError('')
    setLoading(true)
    try {
      const data = await guestApi()
      localStorage.setItem('lexia_token', data.access_token)
      localStorage.setItem('lexia_user', JSON.stringify({ id: data.user_id, username: 'Invitado', is_guest: true, queries_remaining: data.guest_queries_remaining }))
      router.push('/chat')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-lexia-900 to-lexia-600 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-lexia-500 rounded-2xl mb-4">
            <span className="text-white text-2xl font-bold">⚖</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-800">Lexia</h1>
          <p className="text-slate-500 text-sm mt-1">Asistente Legal Boliviano</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Correo electrónico</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-lexia-500 focus:border-transparent"
              placeholder="tu@email.com"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-lexia-500 focus:border-transparent"
              placeholder="••••••••"
              required
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-lexia-500 hover:bg-lexia-600 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors"
          >
            {loading ? 'Ingresando...' : 'Ingresar'}
          </button>
        </form>

        <div className="relative my-5">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center text-xs text-slate-500 bg-white px-2">o</div>
        </div>

        <button
          onClick={handleGuest}
          disabled={loading}
          className="w-full border border-slate-300 hover:bg-slate-50 disabled:opacity-50 text-slate-700 font-medium py-2.5 rounded-lg transition-colors text-sm"
        >
          Continuar como invitado (3 consultas gratis)
        </button>

        <p className="text-center text-sm text-slate-500 mt-6">
          ¿No tienes cuenta?{' '}
          <Link href="/register" className="text-lexia-500 hover:underline font-medium">
            Regístrate gratis
          </Link>
        </p>
      </div>
    </div>
  )
}

'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { signupApi } from '@/lib/api'

export default function RegisterPage() {
  const router = useRouter()
  const [form, setForm] = useState({ email: '', username: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function handle(field) {
    return e => setForm(f => ({ ...f, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirm) { setError('Las contraseñas no coinciden'); return }
    if (form.password.length < 6) { setError('La contraseña debe tener al menos 6 caracteres'); return }
    setLoading(true)
    try {
      const data = await signupApi(form.email, form.username, form.password)
      localStorage.setItem('lexia_token', data.access_token)
      localStorage.setItem('lexia_user', JSON.stringify({ id: data.user_id, username: data.username, is_guest: false }))
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
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-lexia-500 rounded-2xl mb-4">
            <span className="text-white text-2xl font-bold">⚖</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-800">Crear cuenta</h1>
          <p className="text-slate-500 text-sm mt-1">Acceso ilimitado a Lexia</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Correo electrónico</label>
            <input type="email" value={form.email} onChange={handle('email')}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-lexia-500 focus:border-transparent"
              placeholder="tu@email.com" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Nombre de usuario</label>
            <input type="text" value={form.username} onChange={handle('username')}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-lexia-500 focus:border-transparent"
              placeholder="Juan Mamani" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Contraseña</label>
            <input type="password" value={form.password} onChange={handle('password')}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-lexia-500 focus:border-transparent"
              placeholder="Mínimo 6 caracteres" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Confirmar contraseña</label>
            <input type="password" value={form.confirm} onChange={handle('confirm')}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-lexia-500 focus:border-transparent"
              placeholder="Repite tu contraseña" required />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-3 py-2">{error}</div>
          )}

          <button type="submit" disabled={loading}
            className="w-full bg-lexia-500 hover:bg-lexia-600 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors">
            {loading ? 'Creando cuenta...' : 'Crear cuenta'}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500 mt-6">
          ¿Ya tienes cuenta?{' '}
          <Link href="/login" className="text-lexia-500 hover:underline font-medium">Inicia sesión</Link>
        </p>
      </div>
    </div>
  )
}

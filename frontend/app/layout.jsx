import './globals.css'

export const metadata = {
  title: 'Lexia — Asistente Legal Boliviano',
  description: 'Consulta legal inteligente basada en legislación boliviana',
}

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body className="bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  )
}

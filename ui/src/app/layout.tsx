import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ITR Filing Agent',
  description: 'Automated ITR-1 filing for CAs',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <nav className="border-b bg-white px-6 py-4 shadow-sm">
          <span className="text-lg font-semibold">ITR Filing Agent</span>
        </nav>
        <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
      </body>
    </html>
  )
}

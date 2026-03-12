import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'OpenLaw',
  description: 'AI chief of staff for deal lawyers',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

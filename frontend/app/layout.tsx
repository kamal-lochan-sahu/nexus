import type { Metadata } from 'next'
import localFont from 'next/font/local'
import './globals.css'

const geistSans = localFont({ src:'./fonts/GeistVF.woff',      variable:'--font-sans', weight:'100 900' })
const geistMono = localFont({ src:'./fonts/GeistMonoVF.woff',  variable:'--font-mono', weight:'100 900' })

export const metadata: Metadata = {
  title: 'NEXUS — Industry 5.0 Robotics Platform',
  description: 'Unified Robotics Intelligence for Unitree Go2 | Kamal Lochan Sahu',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}
        style={{ background:'var(--bg-primary)', color:'var(--text-primary)', height:'100vh', overflow:'hidden' }}>
        {children}
      </body>
    </html>
  )
}

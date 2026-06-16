import type { Metadata } from 'next'
import localFont from 'next/font/local'
import './globals.css'

const geistSans = localFont({ src:'./fonts/GeistVF.woff',      variable:'--font-sans', weight:'100 900' })
const geistMono = localFont({ src:'./fonts/GeistMonoVF.woff',  variable:'--font-mono', weight:'100 900' })

export const metadata: Metadata = {
  title: 'NEXUS — Industry 5.0 Robotics Platform',
  description: 'Unified Robotics Intelligence for Unitree Go2 | 6 AI modules | Kamal Lochan Sahu',
  metadataBase: new URL('https://nexus-sable-nine.vercel.app'),
  openGraph: {
    title: 'NEXUS — Industry 5.0 Robotics Platform',
    description: '2 Unitree Go2 robots. 6 AI modules. Live dashboard. Built on AMD A4 with 3.3GB RAM.',
    url: 'https://nexus-sable-nine.vercel.app',
    siteName: 'NEXUS',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'NEXUS — Industry 5.0 Robotics Platform Dashboard',
      },
    ],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'NEXUS — Industry 5.0 Robotics Platform',
    description: '2 Unitree Go2 robots. 6 AI modules. Live.',
    images: ['/og-image.png'],
  },
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

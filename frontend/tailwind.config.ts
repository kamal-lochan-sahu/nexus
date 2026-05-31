import type { Config } from 'tailwindcss'
const config: Config = {
  content: ['./app/**/*.{ts,tsx}','./hooks/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-primary':   'var(--bg-primary)',
        'bg-secondary': 'var(--bg-secondary)',
        'bg-card':      'var(--bg-card)',
        'n-border':     'var(--border)',
        'accent-cyan':  'var(--accent-cyan)',
        'accent-purple':'var(--accent-purple)',
        'n-success':    'var(--success)',
        'n-warning':    'var(--warning)',
        'n-danger':     'var(--danger)',
        'text-sec':     'var(--text-secondary)',
      },
      fontFamily: {
        mono: ['var(--font-mono)','JetBrains Mono','monospace'],
        sans: ['var(--font-sans)','Inter','sans-serif'],
      },
    },
  },
  plugins: [],
}
export default config

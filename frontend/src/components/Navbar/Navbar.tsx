import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { useTheme } from '../../contexts/ThemeContext'
import LanguageToggle from '../LanguageToggle/LanguageToggle'

function ThemeToggle() {
  const { t } = useTranslation()
  const { mode, setMode } = useTheme()
  const modes = ['light', 'dark', 'system'] as const
  const next = () => setMode(modes[(modes.indexOf(mode) + 1) % modes.length])
  const icon = { light: '☀️', dark: '🌙', system: '🖥️' }[mode]
  return (
    <button
      type="button"
      onClick={next}
      title={t('nav.theme', { mode })}
      aria-label={t('nav.theme', { mode })}
      className="rounded-md p-1.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
    >
      <span aria-hidden>{icon}</span>
    </button>
  )
}

function UserMenu() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  if (!user) return null
  const label = user.email || user.username
  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-800"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700 dark:bg-blue-900 dark:text-blue-300">
          {label.charAt(0).toUpperCase()}
        </span>
        <span className="hidden text-sm text-slate-700 md:inline dark:text-slate-300">{label}</span>
      </button>
      {open && (
        <div className="absolute end-0 top-full z-50 mt-1.5 w-44 rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800">
          <button
            type="button"
            onClick={logout}
            className="w-full px-4 py-2 text-start text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
          >
            {t('nav.signOut')}
          </button>
        </div>
      )}
    </div>
  )
}

export default function Navbar() {
  const { t } = useTranslation()
  const { user, loading } = useAuth()
  return (
    <nav className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-baseline gap-2 text-slate-900 dark:text-slate-100">
          <span className="text-base font-bold tracking-tight">{t('app.title')}</span>
          <span className="hidden text-xs text-slate-500 sm:inline dark:text-slate-400">{t('app.tagline')}</span>
        </Link>
        <div className="flex items-center gap-1">
          <LanguageToggle />
          <ThemeToggle />
          <div className="mx-1 h-5 w-px bg-slate-200 dark:bg-slate-700" />
          {loading ? (
            <div className="h-7 w-16 animate-pulse rounded-md bg-slate-100 dark:bg-slate-800" />
          ) : user ? (
            <UserMenu />
          ) : (
            <a href="/accounts/google/login/?process=login" className="btn-secondary px-3 py-1.5 text-xs">
              <span className="hidden sm:inline">{t('nav.signIn')}</span>
              <span className="sm:hidden">{t('nav.signInShort')}</span>
            </a>
          )}
        </div>
      </div>
    </nav>
  )
}

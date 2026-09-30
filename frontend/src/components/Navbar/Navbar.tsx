import { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { useTheme } from '../../contexts/ThemeContext'

function ThemeToggle() {
  const { mode, setMode } = useTheme()
  const modes = ['light', 'dark', 'system'] as const
  const next = () => {
    const i = modes.indexOf(mode)
    setMode(modes[(i + 1) % modes.length])
  }
  return (
    <button
      onClick={next}
      className="p-1.5 rounded-md text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors"
      title={`Theme: ${mode}`}
    >
      {mode === 'light' && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      )}
      {mode === 'dark' && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      )}
      {mode === 'system' && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  )
}

export default function Navbar() {
  const { user, loading, logout } = useAuth()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    setMenuOpen(false)
    setMobileMenuOpen(false)
  }, [location.pathname])

  return (
    <nav className="bg-white border-b border-slate-200 dark:bg-slate-900 dark:border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <Link
            to="/app"
            className="flex items-center gap-2 text-base font-bold tracking-tight text-slate-900 hover:text-blue-600 transition-colors dark:text-slate-100 dark:hover:text-blue-400"
          >
            HealTrip
          </Link>

          <div className="flex items-center gap-1">
            {loading ? (
              <>
                <div className="w-16 h-7 bg-slate-100 dark:bg-slate-800 rounded-md animate-pulse" />
                <div className="w-px h-5 bg-slate-200 dark:bg-slate-700 mx-1" />
                <ThemeToggle />
              </>
            ) : user ? (
              <>
                {/* Desktop user menu */}
                <div className="hidden sm:flex items-center gap-1">
                  <div className="relative" ref={menuRef}>
                    <button
                      onClick={() => setMenuOpen(!menuOpen)}
                      className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                      {user.avatar_url ? (
                        <img
                          src={user.avatar_url}
                          alt={user.username}
                          className="w-7 h-7 rounded-full ring-1 ring-slate-200 dark:ring-slate-700"
                        />
                      ) : (
                        <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold dark:bg-blue-900 dark:text-blue-300">
                          {(user.email || user.username)?.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <span className="text-sm font-medium text-slate-700 hidden md:inline dark:text-slate-300">
                        {user.email || user.username}
                      </span>
                      <svg
                        className={`w-3.5 h-3.5 text-slate-400 transition-transform ${menuOpen ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {menuOpen && (
                      <div className="absolute right-0 top-full mt-1.5 w-48 bg-white rounded-lg border border-slate-200 shadow-lg py-1 z-50 dark:bg-slate-800 dark:border-slate-700">
                        <button
                          onClick={logout}
                          className="flex items-center gap-2.5 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                          </svg>
                          Sign out
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="w-px h-5 bg-slate-200 dark:bg-slate-700 mx-2" />
                </div>
                <ThemeToggle />

                {/* Mobile hamburger button */}
                <div className="sm:hidden ml-1">
                  <button
                    onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                    className="p-1.5 rounded-md text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors"
                  >
                    {mobileMenuOpen ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                      </svg>
                    )}
                  </button>
                </div>
              </>
            ) : (
              <>
                <a
                  href="/accounts/google/login/?process=login"
                  className="btn-primary text-sm"
                >
                  <span className="hidden sm:inline">Sign in with Google</span>
                  <span className="sm:hidden">Sign in</span>
                </a>
                <div className="w-px h-5 bg-slate-200 dark:bg-slate-700 mx-1" />
                <ThemeToggle />
              </>
            )}
          </div>
        </div>
      </div>

      {/* Mobile menu overlay */}
      {user && mobileMenuOpen && (
        <div className="sm:hidden fixed inset-0 top-14 z-50">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/30 dark:bg-black/50"
            onClick={() => setMobileMenuOpen(false)}
          />
          {/* Menu panel */}
          <div className="relative bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200/50 dark:border-slate-800/50 shadow-lg">
            <div className="py-2">
              {/* User info */}
              <div className="flex items-center gap-3 px-4 py-2.5">
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.username}
                    className="w-8 h-8 rounded-full ring-1 ring-slate-200 dark:ring-slate-700"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold dark:bg-blue-900 dark:text-blue-300">
                    {(user.email || user.username)?.charAt(0).toUpperCase()}
                  </div>
                )}
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {user.email || user.username}
                </span>
              </div>

              <div className="border-t border-slate-100 dark:border-slate-800 my-1" />

              <button
                onClick={logout}
                className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  )
}

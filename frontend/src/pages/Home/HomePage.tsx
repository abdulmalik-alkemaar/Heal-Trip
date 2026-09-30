import { useAuth } from '../../contexts/AuthContext'

export default function HomePage() {
  const { user, loading } = useAuth()

  return (
    <div>
      {/* Hero */}
      <div className="text-center py-16 sm:py-20">
        <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-slate-100 mb-3 tracking-tight">
          HealTrip
        </h1>
        <p className="text-base sm:text-lg text-slate-500 dark:text-slate-400 max-w-lg mx-auto mb-8 leading-relaxed">
          HealTrip AI Patient Decision Assistant
        </p>

        {loading ? (
          <div className="h-11 w-52 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse mx-auto" />
        ) : user ? (
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <p className="text-slate-600 dark:text-slate-400">
              Welcome back, <span className="font-semibold text-slate-900 dark:text-slate-100">{user.email || user.username}</span>
            </p>
          </div>
        ) : (
          <a
            href="/accounts/google/login/?process=login"
            className="btn-primary inline-flex items-center gap-2"
          >
            Sign in with Google
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M14 5l7 7m0 0l-7 7m7-7H3"
              />
            </svg>
          </a>
        )}
      </div>
    </div>
  )
}

import { useTranslation } from 'react-i18next'
import { BrowserRouter, Outlet, Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar/Navbar'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import ChatPage from './pages/Chat/ChatPage'
import LoginPage from './pages/Login/LoginPage'

function AppLayout() {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 dark:bg-slate-950">
      <Navbar />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-4 sm:px-6 lg:px-8">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white px-4 py-3 text-center text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
        <p>{t('footer.disclaimer')}</p>
        <p className="mt-0.5">{t('footer.fictional')}</p>
      </footer>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route element={<AppLayout />}>
              {/* The chat is public: reviewers need no login (Google sign-in is optional). */}
              <Route path="/" element={<ChatPage />} />
              <Route path="/app" element={<ChatPage />} />
              <Route path="/app/login" element={<LoginPage />} />
            </Route>
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

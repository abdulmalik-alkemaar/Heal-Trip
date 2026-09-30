import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import Navbar from './components/Navbar/Navbar'
import ProtectedRoute from './components/ProtectedRoute/ProtectedRoute'
import HomePage from './pages/Home/HomePage'
import LoginPage from './pages/Login/LoginPage'

function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            {/* App routes with navbar */}
            <Route element={<AppLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/app" element={<HomePage />} />
              <Route path="/app/login" element={<LoginPage />} />

              {/* Protected routes — add your authenticated pages here */}
              <Route element={<ProtectedRoute />}>
                {/* Example: <Route path="/app/dashboard" element={<DashboardPage />} /> */}
              </Route>
            </Route>
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

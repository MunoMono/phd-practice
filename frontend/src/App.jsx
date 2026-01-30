import { useState } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Theme, Loading } from '@carbon/react'
import Header from './components/Header/Header'
import Dashboard from './pages/Dashboard/Dashboard'
import EvidenceTracer from './pages/EvidenceTracer/EvidenceTracer'
import SessionRecorder from './pages/SessionRecorder/SessionRecorder'
import ExperimentalLog from './pages/ExperimentalLog/ExperimentalLog'
import LoginPage from './components/Auth/LoginPage'
import './styles/App.scss'

function App() {
  const [theme, setTheme] = useState('g100')
  const { isAuthenticated, isLoading } = useAuth0()

  const toggleTheme = () => {
    setTheme(prevTheme => prevTheme === 'white' ? 'g100' : 'white')
  }

  if (isLoading) {
    return (
      <Theme theme={theme}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
          <Loading withOverlay={false} />
        </div>
      </Theme>
    )
  }

  if (!isAuthenticated) {
    return (
      <Theme theme={theme}>
        <LoginPage />
      </Theme>
    )
  }

  return (
    <Router>
      <Theme theme={theme}>
        <Header currentTheme={theme} onThemeToggle={toggleTheme} />
        <div className="app-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tracer" element={<EvidenceTracer />} />
            <Route path="/sessions" element={<SessionRecorder />} />
            <Route path="/experiments" element={<ExperimentalLog />} />
          </Routes>
        </div>
      </Theme>
    </Router>
  )
}

export default App

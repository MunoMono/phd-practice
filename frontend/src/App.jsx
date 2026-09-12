import { Suspense, lazy, useState } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Theme, Loading } from '@carbon/react'
import AppShell from './components/AppShell/AppShell'

const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard'))
const CorpusExplorer = lazy(() => import('./pages/CorpusExplorer/CorpusExplorer'))
const EvidenceTracer = lazy(() => import('./pages/EvidenceTracer/EvidenceTracer'))
const VisualAnalytics = lazy(() => import('./pages/VisualAnalytics/VisualAnalytics'))
const SemanticNeighbourhoods = lazy(() => import('./pages/VisualAnalytics/SemanticNeighbourhoods'))
const ComparativeViews = lazy(() => import('./pages/VisualAnalytics/ComparativeViews'))
const TemporalDocumentaryChange = lazy(() => import('./pages/VisualAnalytics/TemporalDocumentaryChange'))
const CriticalInquiry = lazy(() => import('./pages/VisualAnalytics/CriticalInquiry'))
const ChallengeMap = lazy(() => import('./pages/VisualAnalytics/ChallengeMap'))
const MissingnessWorkbench = lazy(() => import('./pages/MissingnessWorkbench/MissingnessWorkbench'))
const CrossReadWorkbench = lazy(() => import('./pages/CrossReadWorkbench/CrossReadWorkbench'))
const ClaimsWorkbench = lazy(() => import('./pages/ClaimsWorkbench/ClaimsWorkbench'))
const AuditWorkbench = lazy(() => import('./pages/AuditWorkbench/AuditWorkbench'))
const ResearchRuns = lazy(() => import('./pages/ResearchRuns/ResearchRuns'))
const Documentation = lazy(() => import('./pages/Documentation/Documentation'))
const LoginPage = lazy(() => import('./components/Auth/LoginPage'))

function App() {
  const [theme, setTheme] = useState('g100')
  const { isAuthenticated, isLoading } = useAuth0()

  const routeFallback = (
    <div className="app-loading-state">
      <Loading withOverlay={false} />
    </div>
  )

  const toggleTheme = () => {
    setTheme(prevTheme => prevTheme === 'white' ? 'g100' : 'white')
  }

  if (isLoading) {
    return (
      <Theme theme={theme}>
        <div className="app-loading-state">
          <Loading withOverlay={false} />
        </div>
      </Theme>
    )
  }

  if (!isAuthenticated) {
    return (
      <Theme theme={theme}>
        <Suspense fallback={routeFallback}>
          <LoginPage />
        </Suspense>
      </Theme>
    )
  }

  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Theme theme={theme}>
        <div className={`ddr-theme ${theme === 'g100' ? 'ddr-theme--dark' : 'ddr-theme--light'}`}>
          <AppShell currentTheme={theme} onThemeToggle={toggleTheme}>
            <div className="app-content">
              <Suspense fallback={routeFallback}>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/workbench" element={<Dashboard />} />
                  <Route path="/dashboard" element={<Navigate to="/workbench" replace />} />
                  <Route path="/sources" element={<CorpusExplorer />} />
                  <Route path="/source-interrogation" element={<EvidenceTracer />} />
                  <Route path="/absences" element={<MissingnessWorkbench />} />
                  <Route path="/cross-readings" element={<CrossReadWorkbench />} />
                  <Route path="/semantic-atlas" element={<VisualAnalytics />} />
                  <Route path="/semantic-neighbourhoods" element={<SemanticNeighbourhoods />} />
                  <Route path="/comparative-views" element={<ComparativeViews />} />
                  <Route path="/temporal-documentary-change" element={<TemporalDocumentaryChange />} />
                  <Route path="/critical-inquiry" element={<CriticalInquiry />} />
                  <Route path="/challenge-map" element={<ChallengeMap />} />
                  <Route path="/claims-evidence" element={<ClaimsWorkbench />} />
                  <Route path="/provenance" element={<AuditWorkbench />} />
                  <Route path="/research-runs" element={<ResearchRuns />} />
                  <Route path="/documentation" element={<Documentation />} />
                  <Route path="/documentation/:docId" element={<Documentation />} />
                  <Route path="/corpus" element={<Navigate to="/sources" replace />} />
                  <Route path="/ask" element={<Navigate to="/source-interrogation" replace />} />
                  <Route path="/missingness" element={<Navigate to="/absences" replace />} />
                  <Route path="/cross-read" element={<Navigate to="/cross-readings" replace />} />
                  <Route path="/clusters" element={<Navigate to="/semantic-atlas" replace />} />
                  <Route path="/claims" element={<Navigate to="/claims-evidence" replace />} />
                  <Route path="/audit" element={<Navigate to="/provenance" replace />} />
                  <Route path="/tracer" element={<Navigate to="/source-interrogation" replace />} />
                  <Route path="/visual-analytics" element={<Navigate to="/semantic-atlas" replace />} />
                  <Route path="/sessions" element={<Navigate to="/provenance" replace />} />
                  <Route path="/experiments" element={<Navigate to="/research-runs" replace />} />
                  <Route path="/ml-dashboard" element={<Navigate to="/provenance" replace />} />
                </Routes>
              </Suspense>
            </div>
          </AppShell>
        </div>
      </Theme>
    </Router>
  )
}

export default App

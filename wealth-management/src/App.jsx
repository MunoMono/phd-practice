import { useState, useEffect } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Theme, Loading, Button } from '@carbon/react'
import { Download, Reset } from '@carbon/icons-react'
import Header from './components/Header/Header'
import Dashboard from './pages/Dashboard/Dashboard'
import Holdings from './pages/Holdings/Holdings'
import Import from './pages/Import/Import'
import LoginPage from './components/Auth/LoginPage'
import { DEFAULT_PORTFOLIO } from './utils/defaultPortfolio'
import { loadPortfolio, savePortfolio, resetPortfolio } from './utils/localStorage'
import { calculateTotalCurrent, formatCurrency } from './utils/portfolioCalculations'
import { exportToCSV, downloadCSV } from './utils/csvHelpers'
import './styles/App.scss'

function App() {
  const [theme, setTheme] = useState('g100')
  const [portfolio, setPortfolio] = useState(DEFAULT_PORTFOLIO)
  const [activeTab, setActiveTab] = useState('dashboard')
  const { isAuthenticated, isLoading } = useAuth0()

  // Load portfolio from localStorage on mount
  useEffect(() => {
    const loaded = loadPortfolio(DEFAULT_PORTFOLIO);
    console.log('App.jsx loaded portfolio:', loaded);
    console.log('Holdings count:', loaded?.holdings?.length);
    console.log('Sleeves count:', loaded?.sleeves?.length);
    setPortfolio(loaded);
  }, []);

  // Save portfolio to localStorage whenever it changes
  useEffect(() => {
    savePortfolio(portfolio);
  }, [portfolio]);

  const toggleTheme = () => {
    setTheme(prevTheme => prevTheme === 'white' ? 'g100' : 'white')
  }

  const handleUpdateTolerancePct = (newTolerance) => {
    setPortfolio({ ...portfolio, tolerancePct: newTolerance });
  };

  const handleUpdateHolding = (holdingId, updatedHolding) => {
    setPortfolio({
      ...portfolio,
      holdings: portfolio.holdings.map(h => 
        h.id === holdingId ? updatedHolding : h
      )
    });
  };

  const handleDeleteHolding = (holdingId) => {
    setPortfolio({
      ...portfolio,
      holdings: portfolio.holdings.filter(h => h.id !== holdingId)
    });
  };

  const handleAddHolding = (newHolding) => {
    setPortfolio({
      ...portfolio,
      holdings: [...portfolio.holdings, newHolding]
    });
  };

  const handleImportPortfolio = (importedPortfolio) => {
    setPortfolio(importedPortfolio);
  };

  const handleReset = () => {
    if (window.confirm('Reset to default portfolio? This will erase all current data.')) {
      const defaultData = resetPortfolio(DEFAULT_PORTFOLIO);
      setPortfolio(defaultData);
    }
  };

  const handleExport = () => {
    const { csv, filename } = exportToCSV(portfolio);
    downloadCSV(csv, filename);
  };

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

  const totalCurrent = calculateTotalCurrent(portfolio.holdings);

  return (
    <Router>
      <Theme theme={theme}>
        <Header 
          currentTheme={theme} 
          onThemeToggle={toggleTheme}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />
        <div className="app-content">
          {/* Portfolio Summary Header */}
          <div className="portfolio-header">
            <div className="portfolio-info">
              <h2>{portfolio.portfolioName}</h2>
              <div className="portfolio-stats">
                <span className="stat-label">Base Currency:</span>
                <span className="stat-value">{portfolio.baseCurrency}</span>
                <span className="stat-separator">|</span>
                <span className="stat-label">Total Value:</span>
                <span className="stat-value">{formatCurrency(totalCurrent, portfolio.baseCurrency)}</span>
              </div>
            </div>
            <div className="portfolio-actions">
              <Button
                kind="tertiary"
                renderIcon={Download}
                onClick={handleExport}
                size="sm"
              >
                Export CSV
              </Button>
              <Button
                kind="tertiary"
                renderIcon={Reset}
                onClick={handleReset}
                size="sm"
              >
                Reset
              </Button>
            </div>
          </div>

          {/* Page Content */}
          <div className="tab-content" style={{ minHeight: 'calc(100vh - 3rem)' }}>
            {activeTab === 'dashboard' && (
              <Dashboard
                portfolio={portfolio}
                onUpdateTolerancePct={handleUpdateTolerancePct}
              />
            )}
            {activeTab === 'holdings' && (
              <Holdings
                portfolio={portfolio}
                onUpdateHolding={handleUpdateHolding}
                onDeleteHolding={handleDeleteHolding}
                onAddHolding={handleAddHolding}
              />
            )}
            {activeTab === 'import' && (
              <Import
                portfolio={portfolio}
                onImportPortfolio={handleImportPortfolio}
              />
            )}
          </div>
        </div>
      </Theme>
    </Router>
  )
}

export default App

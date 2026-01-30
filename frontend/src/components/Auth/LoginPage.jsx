import { useAuth0 } from '@auth0/auth0-react'
import { Button, Loading } from '@carbon/react'
import { Login, ChevronRight } from '@carbon/icons-react'
import './LoginPage.scss'

function LoginPage() {
  const { loginWithRedirect, isLoading } = useAuth0()

  if (isLoading) {
    return (
      <div className="login-page">
        <Loading withOverlay={false} />
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-background">
        <div className="orbit orbit-1"></div>
        <div className="orbit orbit-2"></div>
        <div className="orbit orbit-3"></div>
        <div className="particle particle-1"></div>
        <div className="particle particle-2"></div>
        <div className="particle particle-3"></div>
        <div className="particle particle-4"></div>
        <div className="particle particle-5"></div>
      </div>
      
      <div className="login-container">
        <div className="login-content">
          <div className="login-brand">
            <div className="brand-icon">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                <path d="M24 4L44 14V34L24 44L4 34V14L24 4Z" stroke="currentColor" strokeWidth="2" fill="none"/>
                <path d="M24 14L34 20V28L24 34L14 28V20L24 14Z" stroke="currentColor" strokeWidth="2" fill="none"/>
                <circle cx="24" cy="24" r="3" fill="currentColor"/>
              </svg>
            </div>
            <h1 className="login-title">Epistemic Drift Research</h1>
          </div>
          
          <p className="login-subtitle">
            Provenance tracking and evidence analysis for PhD research
          </p>
          
          <div className="login-features">
            <div className="feature-item">
              <ChevronRight size={16} />
              <span>Document provenance tracking</span>
            </div>
            <div className="feature-item">
              <ChevronRight size={16} />
              <span>Evidence graph visualization</span>
            </div>
            <div className="feature-item">
              <ChevronRight size={16} />
              <span>ML-powered drift analysis</span>
            </div>
          </div>
          
          <Button
            renderIcon={Login}
            onClick={() => loginWithRedirect()}
            size="lg"
            className="login-button"
          >
            Sign in to continue
          </Button>
          
          <p className="login-footer">
            Royal College of Art • Design PhD Programme
          </p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage

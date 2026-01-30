import { useAuth0 } from '@auth0/auth0-react'
import { Button, Loading } from '@carbon/react'
import { Login } from '@carbon/icons-react'
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
      <div className="login-container">
        <div className="login-content">
          <h1 className="login-title">Epistemic Drift Research</h1>
          <p className="login-subtitle">
            Provenance tracking and evidence analysis for PhD research
          </p>
          <Button
            renderIcon={Login}
            onClick={() => loginWithRedirect()}
            size="lg"
            className="login-button"
          >
            Sign in to continue
          </Button>
        </div>
      </div>
    </div>
  )
}

export default LoginPage

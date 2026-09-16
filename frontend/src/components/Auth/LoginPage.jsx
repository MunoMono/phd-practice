import { useAuth0 } from '@auth0/auth0-react'
import { Loading } from '@carbon/react'
import { useEffect } from 'react'

function LoginPage() {
  const { loginWithRedirect, isLoading } = useAuth0()

  useEffect(() => {
    if (!isLoading) {
      loginWithRedirect()
    }
  }, [isLoading, loginWithRedirect])

  return (
    <div className="app-loading-state login-page login-page--loading">
      <Loading withOverlay={false} />
    </div>
  )
}

export default LoginPage

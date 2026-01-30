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
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      minHeight: '100vh',
      background: '#161616'
    }}>
      <Loading withOverlay={false} />
    </div>
  )
}

export default LoginPage

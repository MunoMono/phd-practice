import React from 'react'
import ReactDOM from 'react-dom/client'
import { Auth0Provider, Auth0Context } from '@auth0/auth0-react'
import '@carbon/styles/css/styles.css'
import App from './App.jsx'
import './styles/index.scss'

const domain = 'dev-i4m880asz7y6j5sk.us.auth0.com'
const clientId = '1s7mH4zeZ1iDyLFcbi6elTNL7fttJwGg'

// Enable a local-only bypass for Auth0 so we can preview without logging in.
const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true'
const mockAuthValue = {
  isAuthenticated: true,
  isLoading: false,
  user: { name: 'Dev Bypass User' },
  loginWithRedirect: async () => {},
  logout: () => {},
  getAccessTokenSilently: async () => 'dev-bypass-token'
}

const Providers = ({ children }) => {
  if (bypassAuth) {
    return (
      <Auth0Context.Provider value={mockAuthValue}>
        {children}
      </Auth0Context.Provider>
    )
  }

  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: window.location.origin
      }}
      cacheLocation="localstorage"
    >
      {children}
    </Auth0Provider>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Providers>
      <App />
    </Providers>
  </React.StrictMode>,
)

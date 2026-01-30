import React from 'react'
import ReactDOM from 'react-dom/client'
import { Auth0Provider } from '@auth0/auth0-react'
import '@carbon/styles/css/styles.css'
import App from './App.jsx'
import './styles/index.scss'

const domain = 'dev-i4m880asz7y6j5sk.us.auth0.com'
const clientId = '1s7mH4zeZ1iDyLFcbi6elTNL7fttJwGg'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: window.location.origin
      }}
      cacheLocation="localstorage"
    >
      <App />
    </Auth0Provider>
  </React.StrictMode>,
)

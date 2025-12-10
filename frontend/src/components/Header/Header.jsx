import {
  Header as CarbonHeader,
  HeaderName,
  HeaderNavigation,
  HeaderMenuItem,
  HeaderGlobalBar,
  HeaderGlobalAction,
  Switcher,
  SwitcherItem,
  SwitcherDivider,
  SkipToContent
} from '@carbon/react'
import { Asleep, Light, UserAvatar } from '@carbon/icons-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import '../../styles/components/Header.scss'

const Header = ({ currentTheme, onThemeToggle }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { loginWithRedirect, logout, isAuthenticated, user } = useAuth0()
  const isDark = currentTheme === 'g100'

  return (
    <CarbonHeader aria-label="Epistemic Drift Research">
      <SkipToContent />
      <HeaderName href="#" prefix="RCA PhD" onClick={(e) => { e.preventDefault(); navigate('/') }}>
        {isAuthenticated ? user.name : 'Graham Newman'}
      </HeaderName>
      <HeaderNavigation aria-label="Research Navigation">
        <HeaderMenuItem
          onClick={() => navigate('/')}
          isCurrentPage={location.pathname === '/'}
        >
          Dashboard
        </HeaderMenuItem>
        <HeaderMenuItem
          onClick={() => navigate('/tracer')}
          isCurrentPage={location.pathname === '/tracer'}
        >
          Evidence Tracer
        </HeaderMenuItem>
        <HeaderMenuItem
          onClick={() => navigate('/sessions')}
          isCurrentPage={location.pathname === '/sessions'}
        >
          Session Recorder
        </HeaderMenuItem>
        <HeaderMenuItem
          onClick={() => navigate('/experiments')}
          isCurrentPage={location.pathname === '/experiments'}
        >
          Experimental Log
        </HeaderMenuItem>
      </HeaderNavigation>
      <HeaderGlobalBar>
        <HeaderGlobalAction
          aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
          tooltipAlignment="end"
          onClick={onThemeToggle}
        >
          {isDark ? <Light size={20} /> : <Asleep size={20} />}
        </HeaderGlobalAction>
        <HeaderGlobalAction
          aria-label={isAuthenticated ? user?.name || 'User' : 'Login'}
          tooltipAlignment="end"
        >
          <UserAvatar size={20} />
          <Switcher aria-label="User Menu">
            {isAuthenticated ? (
              <>
                <SwitcherItem aria-label="Profile">
                  {user?.email}
                </SwitcherItem>
                <SwitcherDivider />
                <SwitcherItem 
                  aria-label="Logout"
                  onClick={() => logout({ returnTo: window.location.origin })}
                >
                  Logout
                </SwitcherItem>
              </>
            ) : (
              <SwitcherItem 
                aria-label="Login"
                onClick={() => loginWithRedirect()}
              >
                Login
              </SwitcherItem>
            )}
          </Switcher>
        </HeaderGlobalAction>
      </HeaderGlobalBar>
    </CarbonHeader>
  )
}

export default Header

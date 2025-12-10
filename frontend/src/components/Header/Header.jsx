import {
  Header as CarbonHeader,
  HeaderName,
  HeaderNavigation,
  HeaderMenuItem,
  HeaderGlobalBar,
  HeaderGlobalAction,
  HeaderPanel,
  Switcher,
  SwitcherItem,
  SwitcherDivider,
  SkipToContent,
  ContentSwitcher,
  Switch
} from '@carbon/react'
import { Asleep, Light, UserAvatar } from '@carbon/icons-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import { useState } from 'react'
import '../../styles/components/Header.scss'

const Header = ({ currentTheme, onThemeToggle }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { loginWithRedirect, logout, isAuthenticated, user } = useAuth0()
  const isDark = currentTheme === 'g100'
  const [isSwitcherOpen, setIsSwitcherOpen] = useState(false)
  const [archiveView, setArchiveView] = useState(0)

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
      <ContentSwitcher 
        selectedIndex={archiveView} 
        onChange={(e) => setArchiveView(e.index)}
        style={{ marginLeft: 'auto', marginRight: '1rem' }}
      >
        <Switch name="public" text="DDR Public Archive" />
        <Switch name="admin" text="DDR Archive Admin" />
      </ContentSwitcher>
      <HeaderGlobalBar>
        <HeaderGlobalAction
          aria-label="User menu"
          tooltipAlignment="end"
          isActive={isSwitcherOpen}
          onClick={() => setIsSwitcherOpen(!isSwitcherOpen)}
        >
          <UserAvatar size={20} />
        </HeaderGlobalAction>
        <HeaderGlobalAction
          aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
          tooltipAlignment="end"
          onClick={onThemeToggle}
        >
          {isDark ? <Light size={20} /> : <Asleep size={20} />}
        </HeaderGlobalAction>
      </HeaderGlobalBar>
      <HeaderPanel aria-label="User menu" expanded={isSwitcherOpen}>
        <Switcher aria-label="User menu">
          {isAuthenticated ? (
            <>
              <SwitcherItem aria-label="User email" isSelected>
                {user?.email}
              </SwitcherItem>
              <SwitcherDivider />
              <SwitcherItem 
                aria-label="Logout"
                onClick={() => {
                  setIsSwitcherOpen(false)
                  logout({ returnTo: window.location.origin })
                }}
              >
                Logout
              </SwitcherItem>
            </>
          ) : (
            <SwitcherItem 
              aria-label="Login"
              onClick={() => {
                setIsSwitcherOpen(false)
                loginWithRedirect()
              }}
            >
              Login
            </SwitcherItem>
          )}
        </Switcher>
      </HeaderPanel>
    </CarbonHeader>
  )
}

export default Header

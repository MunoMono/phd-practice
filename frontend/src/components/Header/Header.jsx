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
  SkipToContent
} from '@carbon/react'
import { Asleep, Light, UserAvatar, Switcher as SwitcherIcon } from '@carbon/icons-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import { useState } from 'react'
import '../../styles/components/Header.scss'

const Header = ({ currentTheme, onThemeToggle }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { loginWithRedirect, logout, isAuthenticated, user } = useAuth0()
  const isDark = currentTheme === 'g100'
  const [isArchiveSwitcherOpen, setIsArchiveSwitcherOpen] = useState(false)
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
      <HeaderGlobalBar>
        <HeaderGlobalAction
          aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
          tooltipAlignment="end"
          onClick={onThemeToggle}
        >
          {isDark ? <Light size={20} /> : <Asleep size={20} />}
        </HeaderGlobalAction>
        <HeaderGlobalAction
          aria-label={isAuthenticated ? 'Logout' : 'Login'}
          tooltipAlignment="end"
          onClick={() => {
            if (isAuthenticated) {
              logout({ returnTo: window.location.origin })
            } else {
              loginWithRedirect()
            }
          }}
        >
          <UserAvatar size={20} />
        </HeaderGlobalAction>
        <HeaderGlobalAction
          aria-label="DDR Archive"
          tooltipAlignment="end"
          isActive={isArchiveSwitcherOpen}
          onClick={() => setIsArchiveSwitcherOpen(!isArchiveSwitcherOpen)}
        >
          <SwitcherIcon size={20} />
        </HeaderGlobalAction>
      </HeaderGlobalBar>
      <HeaderPanel aria-label="DDR Archive" expanded={isArchiveSwitcherOpen}>
        <Switcher aria-label="DDR Archive">
          <SwitcherItem 
            aria-label="DDR Public Archive"
            isSelected={archiveView === 0}
            onClick={() => {
              setArchiveView(0)
              setIsArchiveSwitcherOpen(false)
            }}
          >
            DDR Public Archive
          </SwitcherItem>
          <SwitcherDivider />
          <SwitcherItem 
            aria-label="DDR Archive Admin"
            isSelected={archiveView === 1}
            onClick={() => {
              setArchiveView(1)
              setIsArchiveSwitcherOpen(false)
            }}
          >
            DDR Archive Admin
          </SwitcherItem>
        </Switcher>
      </HeaderPanel>
    </CarbonHeader>
  )
}

export default Header

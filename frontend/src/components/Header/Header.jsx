import {
  Header as CarbonHeader,
  HeaderName,
  HeaderNavigation,
  HeaderMenuItem,
  HeaderMenuButton,
  HeaderGlobalBar,
  HeaderGlobalAction,
  HeaderPanel,
  HeaderSideNavItems,
  SideNav,
  SideNavItems,
  SideNavLink,
  SideNavMenu,
  SideNavMenuItem,
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
  const [isSideNavExpanded, setIsSideNavExpanded] = useState(false)

  const handleNavClick = (path) => {
    navigate(path)
    setIsSideNavExpanded(false)
  }

  return (
    <CarbonHeader aria-label="Epistemic Drift Research">
      <SkipToContent />
      <HeaderMenuButton
        aria-label={isSideNavExpanded ? 'Close menu' : 'Open menu'}
        onClick={() => setIsSideNavExpanded(!isSideNavExpanded)}
        isActive={isSideNavExpanded}
        aria-expanded={isSideNavExpanded}
      />
      <HeaderName href="#" prefix="RCA PhD" onClick={(e) => { e.preventDefault(); navigate('/') }}>
        Graham Newman
      </HeaderName>
      <HeaderNavigation aria-label="Research Navigation" className="desktop-nav">
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
          Evidence tracer
        </HeaderMenuItem>
        <HeaderMenuItem
          onClick={() => navigate('/sessions')}
          isCurrentPage={location.pathname === '/sessions'}
        >
          Session recorder
        </HeaderMenuItem>
        <HeaderMenuItem
          onClick={() => navigate('/experiments')}
          isCurrentPage={location.pathname === '/experiments'}
        >
          Experimental log
        </HeaderMenuItem>
        <HeaderMenuItem
          onClick={() => navigate('/ml-dashboard')}
          isCurrentPage={location.pathname === '/ml-dashboard'}
        >
          ML dashboard
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
        {isAuthenticated && (
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            height: '3rem',
            padding: '0 1rem',
            color: 'var(--cds-text-secondary)',
            fontSize: '0.875rem',
            whiteSpace: 'nowrap',
            border: 'none',
            outline: 'none'
          }}>
            Hello Graham
          </div>
        )}
        <HeaderGlobalAction
          aria-label={isAuthenticated ? 'Logout' : 'Login'}
          tooltipAlignment="end"
          onClick={() => {
            if (isAuthenticated) {
              logout({ 
                logoutParams: {
                  returnTo: 'https://innovationdesign.io'
                }
              })
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
      <SideNav
        aria-label="Side navigation"
        expanded={isSideNavExpanded}
        onOverlayClick={() => setIsSideNavExpanded(false)}
        className="mobile-nav"
      >
        <SideNavItems>
          <SideNavLink
            onClick={() => handleNavClick('/')}
            isActive={location.pathname === '/'}
          >
            Dashboard
          </SideNavLink>
          <SideNavLink
            onClick={() => handleNavClick('/tracer')}
            isActive={location.pathname === '/tracer'}
          >
            Evidence tracer
          </SideNavLink>
          <SideNavLink
            onClick={() => handleNavClick('/sessions')}
            isActive={location.pathname === '/sessions'}
          >
            Session recorder
          </SideNavLink>
          <SideNavLink
            onClick={() => handleNavClick('/experiments')}
            isActive={location.pathname === '/experiments'}
          >
            Experimental log
          </SideNavLink>
          <SideNavLink
            onClick={() => handleNavClick('/ml-dashboard')}
            isActive={location.pathname === '/ml-dashboard'}
          >
            ML Dashboard
          </SideNavLink>
          <SideNavMenu title="DDR Archive">
            <SideNavMenuItem
              onClick={() => {
                setArchiveView(0)
                setIsSideNavExpanded(false)
              }}
            >
              DDR Public Archive
            </SideNavMenuItem>
            <SideNavMenuItem
              onClick={() => {
                setArchiveView(1)
                setIsSideNavExpanded(false)
              }}
            >
              DDR Archive Admin
            </SideNavMenuItem>
          </SideNavMenu>
        </SideNavItems>
      </SideNav>
    </CarbonHeader>
  )
}

export default Header

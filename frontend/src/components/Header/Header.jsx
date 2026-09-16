import {
  Header as CarbonHeader,
  HeaderName,
  HeaderNavigation,
  HeaderMenu,
  HeaderMenuItem,
  HeaderMenuButton,
  HeaderGlobalBar,
  HeaderGlobalAction,
  SideNav,
  SideNavItems,
  SideNavLink,
  SideNavMenu,
  SideNavMenuItem,
  SkipToContent
} from '@carbon/react'
import { Asleep, Light, UserAvatar } from '@carbon/icons-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import { useState } from 'react'
import '../../styles/components/Header.scss'

const topLevelNavigationItems = [
  {
    label: 'Workbench',
    path: '/workbench',
    isActive: (pathname) => pathname === '/' || pathname === '/workbench' || pathname === '/dashboard'
  },
  {
    label: 'Sources',
    path: '/sources',
    isActive: (pathname) => pathname === '/sources' || pathname === '/corpus'
  }
]

const analysisItems = [
  {
    label: 'Source Interrogation',
    path: '/source-interrogation',
    isActive: (pathname) => pathname === '/source-interrogation' || pathname === '/ask' || pathname === '/tracer'
  },
  {
    label: 'Absences',
    path: '/absences',
    isActive: (pathname) => pathname === '/absences' || pathname === '/missingness'
  },
  {
    label: 'Cross-readings',
    path: '/cross-readings',
    isActive: (pathname) => pathname === '/cross-readings' || pathname === '/cross-read'
  },
  {
    label: 'Semantic Atlas',
    path: '/semantic-atlas',
    isActive: (pathname) => pathname === '/semantic-atlas' || pathname === '/clusters' || pathname === '/visual-analytics'
  }
]

const evidenceItems = [
  {
    label: 'Claims & Evidence',
    path: '/claims-evidence',
    isActive: (pathname) => pathname === '/claims-evidence' || pathname === '/claims'
  },
  {
    label: 'Provenance',
    path: '/provenance',
    isActive: (pathname) => pathname === '/provenance' || pathname === '/audit' || pathname === '/sessions' || pathname === '/experiments' || pathname === '/ml-dashboard'
  }
]

const groupedNavigationItems = [
  {
    label: 'Analysis',
    isActive: (pathname) => analysisItems.some((item) => item.isActive(pathname)),
    items: analysisItems
  },
  {
    label: 'Evidence',
    isActive: (pathname) => evidenceItems.some((item) => item.isActive(pathname)),
    items: evidenceItems
  }
]

const Header = ({ currentTheme, onThemeToggle }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { loginWithRedirect, logout, isAuthenticated } = useAuth0()
  const isDark = currentTheme === 'g100'
  const [isSideNavExpanded, setIsSideNavExpanded] = useState(false)

  const handleNavClick = (path) => {
    navigate(path)
    setIsSideNavExpanded(false)
  }

  return (
    <CarbonHeader aria-label="DDR testamentary traces">
      <SkipToContent />
      <HeaderMenuButton
        aria-label={isSideNavExpanded ? 'Close menu' : 'Open menu'}
        onClick={() => setIsSideNavExpanded(!isSideNavExpanded)}
        isActive={isSideNavExpanded}
        isCollapsible
        aria-expanded={isSideNavExpanded}
      />
      <HeaderName href="#" prefix="" onClick={(e) => { e.preventDefault(); navigate('/workbench') }}>
        Graham Newman RCA PhD
      </HeaderName>
      <HeaderNavigation aria-label="Research navigation">
        {topLevelNavigationItems.map((item) => (
          <HeaderMenuItem
            key={item.label}
            onClick={() => navigate(item.path)}
            isActive={item.isActive(location.pathname)}
          >
            {item.label}
          </HeaderMenuItem>
        ))}
        {groupedNavigationItems.map((group) => (
          <HeaderMenu
            key={group.label}
            aria-label={group.label}
            menuLinkName={group.label}
            isActive={group.isActive(location.pathname)}
          >
            {group.items.map((item) => (
              <HeaderMenuItem
                key={item.label}
                onClick={() => navigate(item.path)}
                isActive={item.isActive(location.pathname)}
              >
                {item.label}
              </HeaderMenuItem>
            ))}
          </HeaderMenu>
        ))}
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
      </HeaderGlobalBar>
      <SideNav
        aria-label="Side navigation"
        expanded={isSideNavExpanded}
        isPersistent={false}
        onOverlayClick={() => setIsSideNavExpanded(false)}
      >
        <SideNavItems>
          {topLevelNavigationItems.map((item) => (
            <SideNavLink
              key={item.label}
              onClick={() => handleNavClick(item.path)}
              isActive={item.isActive(location.pathname)}
            >
              {item.label}
            </SideNavLink>
          ))}
          {groupedNavigationItems.map((group) => (
            <SideNavMenu key={group.label} title={group.label} isActive={group.isActive(location.pathname)}>
              {group.items.map((item) => (
                <SideNavMenuItem
                  key={item.label}
                  onClick={() => handleNavClick(item.path)}
                  isActive={item.isActive(location.pathname)}
                >
                  {item.label}
                </SideNavMenuItem>
              ))}
            </SideNavMenu>
          ))}
        </SideNavItems>
      </SideNav>
    </CarbonHeader>
  )
}

export default Header

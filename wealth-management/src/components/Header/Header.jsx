import {
  Header as CarbonHeader,
  HeaderName,
  HeaderNavigation,
  HeaderMenuItem,
  HeaderGlobalBar,
  HeaderGlobalAction,
  SkipToContent
} from '@carbon/react'
import { Asleep, Light, UserAvatar } from '@carbon/icons-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import '../../styles/components/Header.scss'

const Header = ({ currentTheme, onThemeToggle, activeTab, onTabChange }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { logout, isAuthenticated } = useAuth0()
  const isDark = currentTheme === 'g100'

  return (
    <CarbonHeader aria-label="Wealth Management">
      <SkipToContent />
      <HeaderName href="#" prefix="" onClick={(e) => { e.preventDefault(); onTabChange('dashboard'); }}>
        Wealth Management
      </HeaderName>
      <HeaderNavigation aria-label="Navigation">
        <HeaderMenuItem
          onClick={() => onTabChange('dashboard')}
          isCurrentPage={activeTab === 'dashboard'}
        >
          Dashboard
        </HeaderMenuItem>
        <HeaderMenuItem
          onClick={() => onTabChange('holdings')}
          isCurrentPage={activeTab === 'holdings'}
        >
          Holdings
        </HeaderMenuItem>
        <HeaderMenuItem
          onClick={() => onTabChange('import')}
          isCurrentPage={activeTab === 'import'}
        >
          Import/Export
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
            whiteSpace: 'nowrap'
          }}>
            Hello Graham
          </div>
        )}
        <HeaderGlobalAction
          aria-label="Logout"
          tooltipAlignment="end"
          onClick={() => {
            logout({ 
              logoutParams: {
                returnTo: 'https://wealth-management.innovationdesign.io'
              }
            })
          }}
        >
          <UserAvatar size={20} />
        </HeaderGlobalAction>
      </HeaderGlobalBar>
    </CarbonHeader>
  )
}

export default Header

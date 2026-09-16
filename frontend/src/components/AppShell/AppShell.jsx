import { useState } from 'react'
import {
  Breadcrumb,
  BreadcrumbItem,
  Header as CarbonHeader,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuButton,
  HeaderMenuItem,
  HeaderName,
  HeaderNavigation,
  SideNav,
  SideNavItems,
  SideNavLink,
  SkipToContent,
} from '@carbon/react'
import { Asleep, ChevronLeft, ChevronRight, Light, UserAvatar } from '@carbon/icons-react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import { getNavigationContext, PRIMARY_SECTIONS } from './navigation'

const PrimaryNavigation = ({ activeSectionKey, onNavigate }) => (
  <HeaderNavigation aria-label="Primary navigation" className="ddr-app-shell-header__primary-nav">
    {PRIMARY_SECTIONS.map((section) => (
      <HeaderMenuItem
        key={section.key}
        href={section.path}
        isActive={activeSectionKey === section.key}
        onClick={(event) => {
          event.preventDefault()
          onNavigate(section.path)
        }}
      >
        {section.label}
      </HeaderMenuItem>
    ))}
  </HeaderNavigation>
)

const SecondaryNavigation = ({
  sectionLabel,
  items,
  activeItemKey,
  isCollapsed,
  onToggleCollapse,
}) => (
  <aside
    className={`ddr-app-shell__sidebar${isCollapsed ? ' ddr-app-shell__sidebar--collapsed' : ''}`}
    aria-label={`${sectionLabel} navigation`}
  >
    <div className="ddr-app-shell__sidebar-header">
      <div className="ddr-app-shell__sidebar-context">
        <div className="ddr-app-shell__sidebar-eyebrow">{sectionLabel}</div>
        <div className="ddr-app-shell__sidebar-title">Module navigation</div>
      </div>
      <button
        type="button"
        className="ddr-app-shell__sidebar-toggle"
        aria-label={isCollapsed ? `Expand ${sectionLabel} navigation` : `Collapse ${sectionLabel} navigation`}
        aria-pressed={isCollapsed}
        onClick={onToggleCollapse}
      >
        {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </div>
    <nav className="ddr-app-shell__sidebar-nav">
      {items.map((item) => {
        const Icon = item.icon

        return (
          <NavLink
            key={item.key}
            to={item.path}
            title={isCollapsed ? item.label : undefined}
            className={({ isActive }) => `ddr-app-shell__sidebar-link${isActive || activeItemKey === item.key ? ' ddr-app-shell__sidebar-link--active' : ''}`}
          >
            <span className="ddr-app-shell__sidebar-link-icon" aria-hidden="true">
              <Icon size={18} />
            </span>
            <span className="ddr-app-shell__sidebar-link-label">{item.label}</span>
          </NavLink>
        )
      })}
    </nav>
  </aside>
)

const AppShell = ({ currentTheme, onThemeToggle, children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { loginWithRedirect, logout, isAuthenticated, user } = useAuth0()
  const [isMobileNavExpanded, setIsMobileNavExpanded] = useState(false)
  const [isDesktopSidebarCollapsed, setIsDesktopSidebarCollapsed] = useState(false)
  const isDark = currentTheme === 'g100'
  const navigationContext = getNavigationContext(location.pathname)
  const isVisualAnalyticsWorkspace = navigationContext.primarySection.key === 'visual-analytics'
  const secondaryItems = isVisualAnalyticsWorkspace ? [] : navigationContext.secondaryItems
  const breadcrumbs = isVisualAnalyticsWorkspace ? [] : navigationContext.breadcrumbs
  const greetingName = user?.given_name || user?.name?.split(' ')?.[0] || user?.email?.split('@')?.[0] || 'there'

  const handleNavigate = (path) => {
    navigate(path)
    setIsMobileNavExpanded(false)
  }

  return (
    <>
      <CarbonHeader aria-label="DDR testamentary traces" className="ddr-app-shell-header">
        <SkipToContent />
        <HeaderMenuButton
          aria-label={isMobileNavExpanded ? 'Close navigation' : 'Open navigation'}
          className="ddr-app-shell-header__menu-button"
          isActive={isMobileNavExpanded}
          onClick={() => setIsMobileNavExpanded((value) => !value)}
        />
        <HeaderName href="/workbench" prefix="" onClick={(event) => {
          event.preventDefault()
          handleNavigate('/workbench')
        }}>
          <span className="ddr-app-shell-header__brand-name">Graham Newman</span>{' '}
          <span className="ddr-app-shell-header__brand-suffix">RCA PhD</span>
        </HeaderName>
        <PrimaryNavigation
          activeSectionKey={navigationContext.primarySection.key}
          onNavigate={handleNavigate}
        />
        <HeaderGlobalBar>
          <HeaderGlobalAction
            aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            onClick={onThemeToggle}
            tooltipAlignment="end"
          >
            {isDark ? <Light size={20} /> : <Asleep size={20} />}
          </HeaderGlobalAction>
          {isAuthenticated ? <div className="ddr-app-shell-header__greeting">Hello {greetingName}</div> : null}
          <HeaderGlobalAction
            aria-label={isAuthenticated ? 'Logout' : 'Login'}
            onClick={() => {
              if (isAuthenticated) {
                logout({
                  logoutParams: {
                    returnTo: 'https://innovationdesign.io',
                  },
                })
              } else {
                loginWithRedirect()
              }
            }}
            tooltipAlignment="end"
          >
            <UserAvatar size={20} />
          </HeaderGlobalAction>
        </HeaderGlobalBar>
      </CarbonHeader>

      {isMobileNavExpanded ? (
        <SideNav
          aria-label="Application navigation"
          className="ddr-app-shell-mobile-nav"
          expanded
          onOverlayClick={() => setIsMobileNavExpanded(false)}
        >
          <div className="ddr-app-shell-mobile-nav__section-label">Primary navigation</div>
          <SideNavItems>
            {PRIMARY_SECTIONS.map((section) => (
              <SideNavLink
                key={section.key}
                href={section.path}
                isActive={navigationContext.primarySection.key === section.key}
                onClick={(event) => {
                  event.preventDefault()
                  handleNavigate(section.path)
                }}
                renderIcon={section.icon}
              >
                {section.label}
              </SideNavLink>
            ))}
          </SideNavItems>

          {secondaryItems.length ? (
            <>
              <div className="ddr-app-shell-mobile-nav__section-label">
                {navigationContext.primarySection.label}
              </div>
              <SideNavItems>
                {secondaryItems.map((item) => (
                  <SideNavLink
                    key={item.key}
                    href={item.path}
                    isActive={navigationContext.activeSecondaryItem?.key === item.key}
                    onClick={(event) => {
                      event.preventDefault()
                      handleNavigate(item.path)
                    }}
                    renderIcon={item.icon}
                  >
                    {item.label}
                  </SideNavLink>
                ))}
              </SideNavItems>
            </>
          ) : null}
        </SideNav>
      ) : null}

      <div
        className={`ddr-app-shell${secondaryItems.length ? ' ddr-app-shell--with-sidebar' : ''}${isDesktopSidebarCollapsed ? ' ddr-app-shell--sidebar-collapsed' : ''}`}
      >
        {secondaryItems.length ? (
          <SecondaryNavigation
            activeItemKey={navigationContext.activeSecondaryItem?.key}
            isCollapsed={isDesktopSidebarCollapsed}
            items={secondaryItems}
            onToggleCollapse={() => setIsDesktopSidebarCollapsed((value) => !value)}
            sectionLabel={navigationContext.primarySection.label}
          />
        ) : null}

        <main
          id="main-content"
          className={`ddr-app-shell__main${secondaryItems.length ? '' : ' ddr-app-shell__main--standalone'}`}
        >
          {breadcrumbs.length ? (
            <div className="ddr-app-shell__breadcrumbs">
              <Breadcrumb noTrailingSlash>
                {breadcrumbs.map((item) => (
                  <BreadcrumbItem key={item.key}>
                    <Link to={item.path}>{item.label}</Link>
                  </BreadcrumbItem>
                ))}
              </Breadcrumb>
            </div>
          ) : null}
          <div className="ddr-app-shell__content">{children}</div>
        </main>
      </div>
    </>
  )
}

export default AppShell
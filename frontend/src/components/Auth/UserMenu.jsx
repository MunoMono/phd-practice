import { useAuth0 } from '@auth0/auth0-react'
import { HeaderGlobalAction } from '@carbon/react'
import { UserAvatar, Logout } from '@carbon/icons-react'

function UserMenu() {
  const { user, logout } = useAuth0()

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem' }}>
        {user?.email}
      </span>
      <HeaderGlobalAction
        aria-label="User profile"
        tooltipAlignment="end"
      >
        <UserAvatar size={20} />
      </HeaderGlobalAction>
      <HeaderGlobalAction
        aria-label="Logout"
        onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
        tooltipAlignment="end"
      >
        <Logout size={20} />
      </HeaderGlobalAction>
    </div>
  )
}

export default UserMenu

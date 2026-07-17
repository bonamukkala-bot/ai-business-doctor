import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'

const PAGE_TITLES = {
  '/dashboard': 'Dashboard',
  '/sales': 'Sales & Profit',
  '/inventory': 'Inventory',
  '/advisors': 'Advisors',
  '/consult': 'Consult',
  '/settings': 'Settings',
}

export default function DashboardLayout({ user, pageTitle, healthStatus, reportLink }) {
  const location = useLocation()
  const title = pageTitle || PAGE_TITLES[location.pathname] || 'Dashboard'

  return (
    <div className="dashboard-shell">
      <Sidebar user={user} />
      <div className="dashboard-main">
        <Topbar title={title} healthStatus={healthStatus} reportLink={reportLink} />
        <main className="dashboard-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

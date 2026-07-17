import { NavLink } from 'react-router-dom'
import { LayoutGrid, TrendingUp, Box, Users, MessageCircle, Settings, Menu } from 'lucide-react'
import { useState } from 'react'

const links = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  { to: '/sales', label: 'Sales & Profit', icon: TrendingUp },
  { to: '/inventory', label: 'Inventory', icon: Box },
  { to: '/advisors', label: 'Advisors', icon: Users },
  { to: '/consult', label: 'Consult', icon: MessageCircle },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar({ user }) {
  const [open, setOpen] = useState(false)
  const shopName = user?.user_metadata?.shop_name || user?.email?.split('@')[0] || 'Business Doctor'

  return (
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <div className="sidebar-mobile-toggle">
        <button type="button" className="icon-btn" onClick={() => setOpen(!open)} aria-label="Toggle navigation">
          <Menu size={20} />
        </button>
        <div className="sidebar-brand-mobile">{shopName}</div>
      </div>

      <div className="sidebar-top">
        <div className="sidebar-brand">
          <div className="sidebar-logo">AI</div>
          <div>
            <p className="sidebar-title">Business Doctor</p>
            <p className="sidebar-shop">{shopName}</p>
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {links.map((link) => {
          const Icon = link.icon
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
              onClick={() => setOpen(false)}
            >
              <Icon size={18} className="sidebar-icon" />
              <span>{link.label}</span>
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}

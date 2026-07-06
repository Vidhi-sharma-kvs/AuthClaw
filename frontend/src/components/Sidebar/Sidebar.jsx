import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Terminal,
  CheckSquare,
  ShieldCheck,
  FileText,
  Activity,
  BarChart3,
  Building2,
  Server,
  ShieldAlert,
  Settings as SettingsIcon,
  LogOut,
  X
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const ROUTE_PERMISSIONS = {
  '/platform/dashboard': ['Platform Admin'],
  '/dashboard': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer', 'Auditor', 'Viewer'],
  '/observability': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer', 'Auditor', 'Viewer'],
  '/chat': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer'],
  '/providers': ['Super Admin', 'Security Admin', 'Developer'],
  '/api-keys': ['Super Admin', 'Security Admin', 'Developer'],
  '/policies': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer'],
  '/requests': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer', 'Auditor'],
  '/approvals': ['Super Admin', 'Security Admin', 'Compliance Officer'],
  '/audit': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Auditor'],
  '/settings': ['Super Admin', 'Security Admin']
};

const Sidebar = ({ isOpen, toggleSidebar }) => {
  const { user, logout } = useAuth();

  const platformNavItems = [
    { name: 'Platform Dashboard', path: '/platform/dashboard', icon: Building2 },
  ];

  const tenantNavItems = [
    { name: 'Gateway Chat', path: '/chat', icon: Terminal },
    { name: 'Observability', path: '/observability', icon: BarChart3 },
    { name: 'Policies', path: '/policies', icon: ShieldAlert },
    { name: 'Requests', path: '/requests', icon: Activity },
    { name: 'Approval Center', path: '/approvals', icon: CheckSquare },
    { name: 'Audit Logs', path: '/audit', icon: ShieldCheck },
    { name: 'Providers', path: '/providers', icon: Server },
    { name: 'API Keys', path: '/api-keys', icon: FileText },
    { name: 'Settings', path: '/settings', icon: SettingsIcon },
  ];

  const navItems = user?.role === 'Platform Admin' ? platformNavItems : tenantNavItems;

  const allowedNavItems = navItems.filter((item) => {
    const allowedRoles = ROUTE_PERMISSIONS[item.path];
    return allowedRoles ? allowedRoles.includes(user?.role) : true;
  });

  return (
    <aside className={`fixed inset-y-0 left-0 z-40 w-64 bg-[#08152B] border-r border-[#1B3663]/30 transition-transform duration-300 transform ${isOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 lg:static lg:inset-0 flex flex-col shrink-0`}>

      {/* Logo Section */}
      <div className="h-16 flex items-center justify-between px-6 border-b border-[#1B3663]/20 bg-black/10 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-tr from-[#6D28D9] to-[#1B3663] rounded-lg shadow-lg shadow-violet-500/10">
            <ShieldAlert className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-lg bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent font-display tracking-tight">
            AuthClaw
          </span>
        </div>
        <button
          onClick={toggleSidebar}
          className="lg:hidden text-gray-400 hover:text-white focus:outline-none"
          aria-label="Close navigation"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scrollable Nav Area */}
      <div className="flex-1 overflow-y-auto">
        {/* Navigation Items */}
        <nav className="mt-6 px-4 space-y-1.5">
          {allowedNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3.5 px-4 py-2.5 rounded-lg text-xs font-semibold tracking-wide transition-all duration-200 group ${
                    isActive
                      ? 'bg-[#6D28D9]/15 border-l-2 border-[#6D28D9] text-white shadow-inner font-display'
                      : 'text-gray-400 hover:bg-white/[0.03] hover:text-white border-l-2 border-transparent'
                  }`
                }
                onClick={() => {
                  if (window.innerWidth < 1024) toggleSidebar();
                }}
              >
                <Icon className="w-4 h-4 transition-transform group-hover:scale-110" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* User Card */}
        {user && (
          <div className="px-4 pt-3 pb-2">
            <div className="flex items-center gap-3 bg-white/[0.02] border border-white/5 p-2.5 rounded-lg">
              <div className="w-9 h-9 rounded-full bg-[#6D28D9] border border-violet-500/20 flex items-center justify-center font-bold text-white text-xs uppercase shadow-inner shrink-0 font-display">
                {user.username.charAt(0)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-bold text-white truncate">{user.username}</p>
                <p className="text-[9px] text-gray-500 truncate font-mono uppercase font-bold">{user.role}</p>
              </div>
              <button
                onClick={logout}
                className="p-1.5 hover:bg-white/5 text-gray-400 hover:text-rose-400 rounded-lg transition-colors shrink-0"
                title="Logout session"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-[#1B3663]/20 bg-black/10 text-center shrink-0">
        <span className="text-[9px] text-gray-600 tracking-wider font-mono">AuthClaw v2.0.0 | Production Admin</span>
      </div>

    </aside>
  );
};

export default Sidebar;

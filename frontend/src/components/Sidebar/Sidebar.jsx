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
  CreditCard,
  FileCheck2,
  PlugZap,
  Server,
  ShieldAlert,
  Settings as SettingsIcon,
  Target,
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
  '/connectors': ['Super Admin', 'Security Admin', 'Developer'],
  '/api-keys': ['Super Admin', 'Security Admin', 'Developer'],
  '/trust': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Auditor', 'Viewer'],
  '/frameworks/explorer': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Auditor', 'Viewer'],
  '/red-team': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Auditor'],
  '/tenant-plan': ['Super Admin', 'Security Admin'],
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
    { name: 'Connectors', path: '/connectors', icon: PlugZap },
    { name: 'API Keys', path: '/api-keys', icon: FileText },
    { name: 'Trust Center', path: '/trust', icon: ShieldCheck },
    { name: 'Frameworks', path: '/frameworks/explorer', icon: FileCheck2 },
    { name: 'Red Team', path: '/red-team', icon: Target },
    { name: 'Tenant Plan', path: '/tenant-plan', icon: CreditCard },
    { name: 'Settings', path: '/settings', icon: SettingsIcon },
  ];

  const navItems = user?.role === 'Platform Admin' ? platformNavItems : tenantNavItems;

  const allowedNavItems = navItems.filter((item) => {
    const allowedRoles = ROUTE_PERMISSIONS[item.path];
    return allowedRoles ? allowedRoles.includes(user?.role) : true;
  });

  return (
    <aside className={`fixed inset-y-0 left-0 z-40 w-64 bg-[#FBFAF9]/95 border-r border-[#E6E9F0] shadow-[0_1px_2px_rgba(11,31,63,0.05),0_18px_44px_-28px_rgba(11,31,63,0.45)] backdrop-blur-xl transition-transform duration-300 transform ${isOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 lg:static lg:inset-0 flex flex-col shrink-0`}>

      {/* Logo Section */}
      <div className="h-16 flex items-center justify-between px-6 border-b border-[#E6E9F0] bg-white/80 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-[linear-gradient(135deg,#6D28D9_0%,#E9A93C_100%)] rounded-lg shadow-[0_10px_24px_-12px_rgba(109,40,217,0.7)]">
            <ShieldAlert className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-lg text-[#0E1726] font-display tracking-tight">
            Auth<span className="text-[#6D28D9]">Claw</span>
          </span>
        </div>
        <button
          onClick={toggleSidebar}
          className="lg:hidden text-[#6B7488] hover:text-[#0E1726] focus:outline-none"
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
                      ? 'bg-[#F1ECFE] border-l-2 border-[#6D28D9] text-[#0E1726] shadow-[inset_0_0_0_1px_rgba(167,139,250,0.22)] font-display'
                      : 'text-[#475069] hover:bg-white hover:text-[#0E1726] border-l-2 border-transparent hover:shadow-[0_8px_22px_-16px_rgba(11,31,63,0.28)]'
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
            <div className="flex items-center gap-3 bg-white/85 border border-[#E6E9F0] p-2.5 rounded-lg shadow-[0_8px_24px_-18px_rgba(11,31,63,0.32)]">
              <div className="w-9 h-9 rounded-full bg-[#F1ECFE] border border-[#A78BFA]/40 flex items-center justify-center font-bold text-[#6D28D9] text-xs uppercase shrink-0 font-display">
                {user.username.charAt(0)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-bold text-[#0E1726] truncate">{user.username}</p>
                <p className="text-[9px] text-[#6B7488] truncate font-mono uppercase font-bold">{user.role}</p>
              </div>
              <button
                onClick={logout}
                className="p-1.5 hover:bg-rose-50 text-[#6B7488] hover:text-rose-600 rounded-lg transition-colors shrink-0"
                title="Logout session"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-[#E6E9F0] bg-white/70 text-center shrink-0">
        <span className="text-[9px] text-[#6B7488] tracking-wider font-mono">AuthClaw.ai | Gateway Runtime</span>
      </div>

    </aside>
  );
};

export default Sidebar;

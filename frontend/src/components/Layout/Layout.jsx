import React, { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import Sidebar from '../Sidebar/Sidebar';
import { ExternalLink, Menu, ShieldCheck } from 'lucide-react';

const pageTitleMap = {
  '/app': 'Console Home',
  '/platform/dashboard': 'Platform Administration',
  '/dashboard': 'Gateway Dashboard',
  '/observability': 'Observability',
  '/chat': 'Gateway Chat',
  '/policies': 'Policies',
  '/requests': 'Gateway Requests',
  '/approvals': 'Approval Center',
  '/audit': 'Audit Logs',
  '/providers': 'Providers',
  '/connectors': 'Connectors',
  '/api-keys': 'API Keys',
  '/settings': 'Settings',
};

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const pageTitle = pageTitleMap[location.pathname] || 'Gateway Console';

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <div className="flex min-h-screen bg-[#FBFAF9] text-[#0E1726]">
      {/* Sidebar navigation */}
      <Sidebar isOpen={sidebarOpen} toggleSidebar={toggleSidebar} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-16 flex items-center justify-between px-4 sm:px-6 border-b border-[#E6E9F0] bg-[#FBFAF9]/90 backdrop-blur-xl z-30 shadow-[0_1px_2px_rgba(11,31,63,0.05)]">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={toggleSidebar}
              className="lg:hidden p-2 text-[#6B7488] hover:text-[#0E1726] hover:bg-[#F1ECFE] rounded-lg focus:outline-none"
              aria-label="Open navigation"
            >
              <Menu className="w-6 h-6" />
            </button>
            <div className="hidden min-w-0 lg:block">
              <p className="text-sm font-bold text-[#0E1726] font-display tracking-wide truncate">{pageTitle}</p>
              <p className="text-[10px] text-[#6D28D9] font-mono uppercase tracking-wider font-semibold">Inline AI governance runtime</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <Link
              to="/trust"
              className="hidden sm:inline-flex items-center gap-2 rounded-lg border border-[#E6E9F0] bg-white px-3 py-2 text-xs font-semibold text-[#475069] hover:border-[#A78BFA] hover:text-[#6D28D9] transition-colors"
            >
              Trust Center
              <ShieldCheck className="w-3.5 h-3.5" />
            </Link>
            <Link
              to="/"
              className="hidden sm:inline-flex items-center gap-2 rounded-lg border border-[#E6E9F0] bg-white px-3 py-2 text-xs font-semibold text-[#475069] hover:border-[#A78BFA] hover:text-[#6D28D9] transition-colors"
            >
              Public site
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
            <div className="flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-[10px] font-bold text-[#475069] uppercase tracking-wider font-mono">Gateway Online</span>
            </div>
          </div>
        </header>

        {/* Scrollable Container */}
        <main className="flex-1 p-6 overflow-y-auto bg-[radial-gradient(circle_at_top_left,rgba(109,40,217,0.06),transparent_34%),radial-gradient(circle_at_top_right,rgba(233,169,60,0.07),transparent_30%),#FBFAF9]">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;

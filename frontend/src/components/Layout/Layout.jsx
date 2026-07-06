import React, { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import Sidebar from '../Sidebar/Sidebar';
import { ExternalLink, Menu } from 'lucide-react';

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
        <header className="h-16 flex items-center justify-between px-4 sm:px-6 border-b border-[#E6E9F0] bg-white/80 backdrop-blur-md z-30">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={toggleSidebar}
              className="lg:hidden p-2 text-slate-500 hover:text-[#0E1726] hover:bg-slate-100 rounded-lg focus:outline-none"
              aria-label="Open navigation"
            >
              <Menu className="w-6 h-6" />
            </button>
            <div className="hidden min-w-0 lg:block">
              <p className="text-sm font-bold text-[#0E1726] font-display tracking-wide truncate">{pageTitle}</p>
              <p className="text-[10px] text-slate-400 font-mono uppercase tracking-wider font-semibold">Tenant-scoped AI governance console</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="hidden sm:inline-flex items-center gap-2 rounded-lg border border-[#E6E9F0] px-3 py-2 text-xs font-semibold text-slate-600 hover:border-[#6D28D9]/40 hover:text-[#6D28D9] transition-colors"
            >
              Public site
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
            <div className="flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">Gateway Online</span>
            </div>
          </div>
        </header>

        {/* Scrollable Container */}
        <main className="flex-1 p-6 overflow-y-auto bg-[#F5F7FA]/30">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;

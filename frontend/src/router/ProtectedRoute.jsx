import React from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

// Route permissions mapping corresponding to the RBAC guidelines
const ROUTE_PERMISSIONS = {
  '/platform': ['Platform Admin'],
  '/platform/dashboard': ['Platform Admin'],
  '/dashboard': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer', 'Auditor', 'Viewer'],
  '/chat': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer'],
  '/providers': ['Super Admin', 'Security Admin', 'Developer'],
  '/api-keys': ['Super Admin', 'Security Admin', 'Developer'],
  '/policies': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer'],
  '/requests': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer', 'Auditor'],
  '/gateway': ['Super Admin', 'Security Admin', 'Developer'],
  '/gateway/requests': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer', 'Auditor'],
  '/guardrails': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Developer'],
  '/approvals': ['Super Admin', 'Security Admin', 'Compliance Officer'],
  '/audit': ['Super Admin', 'Security Admin', 'Compliance Officer', 'Auditor'],
  '/settings': ['Super Admin', 'Security Admin']
};

const ProtectedRoute = ({ children }) => {
  const { user, isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-gray-400">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-t-transparent border-violet-500 rounded-full animate-spin" />
          <span className="text-xs font-semibold tracking-wider">Verifying Workstation Cleared State...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role permission access for current path
  const currentPath = location.pathname;
  const permissionPath = currentPath.startsWith('/gateway/requests/')
    ? '/gateway/requests'
    : currentPath.startsWith('/requests/')
      ? '/requests'
      : currentPath;
  const allowedRoles = ROUTE_PERMISSIONS[permissionPath];

  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    const homePath = user?.role === 'Platform Admin' ? '/platform/dashboard' : '/dashboard';
    const homeLabel = user?.role === 'Platform Admin' ? 'Return to Platform Dashboard' : 'Return to Security Dashboard';

    return (
      <div className="flex-1 min-h-[70vh] flex items-center justify-center p-6">
        <div className="glass-card max-w-md p-8 text-center border border-rose-500/20 bg-rose-950/5/40 space-y-6">
          <div className="flex justify-center">
            <div className="p-4 bg-rose-500/10 rounded-2xl border border-rose-500/20 text-rose-400">
              <ShieldAlert className="w-10 h-10 animate-pulse" />
            </div>
          </div>
          
          <div className="space-y-2">
            <h2 className="text-lg font-bold text-white">Security Clearance Violation</h2>
            <p className="text-xs text-gray-400 leading-relaxed">
              Your assigned role (<strong className="text-rose-400">{user?.role}</strong>) does not possess sufficient privileges to inspect the route <strong className="text-white font-mono">{currentPath}</strong>.
            </p>
          </div>

          <div className="border-t border-white/5 pt-5 flex justify-center">
            <Link 
              to={homePath} 
              className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-white/10 hover:border-violet-500 text-white rounded-lg text-xs font-semibold transition-all"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> {homeLabel}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return children;
};

export default ProtectedRoute;

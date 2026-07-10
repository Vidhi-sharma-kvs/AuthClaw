import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import { useAuth } from '../context/AuthContext';
import Layout from '../components/Layout/Layout';

const Dashboard = lazy(() => import('../pages/Dashboard/Dashboard'));
const PlatformDashboard = lazy(() => import('../pages/PlatformDashboard/PlatformDashboard'));
const AgentChat = lazy(() => import('../pages/AgentChat/AgentChat'));
const ApprovalQueue = lazy(() => import('../pages/ApprovalQueue/ApprovalQueue'));
const AuditExplorer = lazy(() => import('../pages/AuditExplorer/AuditExplorer'));
const GatewayCenter = lazy(() => import('../pages/GatewayCenter/GatewayCenter'));
const Connectors = lazy(() => import('../pages/Connectors/Connectors'));
const GatewayRequests = lazy(() => import('../pages/GatewayRequests/GatewayRequests'));
const GatewayRequestDetail = lazy(() => import('../pages/GatewayRequests/GatewayRequestDetail'));
const Guardrails = lazy(() => import('../pages/Guardrails/Guardrails'));
const APIKeys = lazy(() => import('../pages/APIKeys/APIKeys'));
const Settings = lazy(() => import('../pages/Settings/Settings'));
const RedTeam = lazy(() => import('../pages/RedTeam/RedTeam'));
const TenantPlan = lazy(() => import('../pages/TenantPlan/TenantPlan'));
const FrameworkExplorer = lazy(() => import('../pages/FrameworkExplorer/FrameworkExplorer'));
const Login = lazy(() => import('../pages/Login/Login'));
const PublicPage = lazy(() => import('../pages/Public/PublicPage'));
const TrustCenter = lazy(() => import('../pages/Public/TrustCenter'));

const RoleHomeRedirect = () => {
  const { user } = useAuth();
  return <Navigate to={user?.role === 'Platform Admin' ? '/platform/dashboard' : '/chat'} replace />;
};

const publicRoutes = [
  { path: '/', page: 'home' },
  { path: '/product', page: 'products' },
  { path: '/products', page: 'products' },
  { path: '/pricing', page: 'pricing' },
  { path: '/security', page: 'security' },
  { path: '/company', page: 'company' },
];

const publicRedirects = [
  { path: '/platform', to: '/products' },
  { path: '/solutions', to: '/products' },
  { path: '/frameworks', to: '/products' },
  { path: '/trust-center', to: '/security' },
  { path: '/resources', to: '/company' },
  { path: '/docs', to: '/company' },
  { path: '/documentation', to: '/company' },
  { path: '/blog', to: '/company' },
  { path: '/about', to: '/company' },
  { path: '/contact', to: '/company' },
  { path: '/book-demo', to: '/company' },
];

const RouteFallback = () => (
  <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center text-sm font-semibold text-[#48536B]">
    Loading AuthClaw...
  </div>
);

const AppRouter = () => {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {publicRoutes.map((route) => (
          <Route key={route.path} path={route.path} element={<PublicPage page={route.page} />} />
        ))}
        {publicRedirects.map((route) => (
          <Route key={route.path} path={route.path} element={<Navigate to={route.to} replace />} />
        ))}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Login initialStep="register" />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/app" element={<RoleHomeRedirect />} />
          <Route path="/platform/dashboard" element={<PlatformDashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/observability" element={<Dashboard />} />
          <Route path="/chat" element={<AgentChat />} />
          <Route path="/policies" element={<Guardrails />} />
          <Route path="/requests" element={<GatewayRequests />} />
          <Route path="/approvals" element={<ApprovalQueue />} />
          <Route path="/audit" element={<AuditExplorer />} />
          <Route path="/providers" element={<GatewayCenter />} />
          <Route path="/connectors" element={<Connectors />} />
          <Route path="/api-keys" element={<APIKeys />} />
          <Route path="/trust" element={<TrustCenter />} />
          <Route path="/frameworks/explorer" element={<FrameworkExplorer />} />
          <Route path="/red-team" element={<RedTeam />} />
          <Route path="/tenant-plan" element={<TenantPlan />} />

          <Route path="/gateway" element={<Navigate to="/providers" replace />} />
          <Route path="/gateway/requests" element={<GatewayRequests />} />
          <Route path="/gateway/requests/:requestId" element={<GatewayRequestDetail />} />
          <Route path="/requests/:requestId" element={<GatewayRequestDetail />} />
          <Route path="/guardrails" element={<Navigate to="/policies" replace />} />
          <Route path="/settings" element={<Settings />} />

          <Route path="*" element={<RoleHomeRedirect />} />
        </Route>
      </Routes>
    </Suspense>
  );
};

export default AppRouter;

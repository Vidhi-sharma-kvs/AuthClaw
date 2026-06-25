import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import { useAuth } from '../context/AuthContext';
import Layout from '../components/Layout/Layout';
import Dashboard from '../pages/Dashboard/Dashboard';
import PlatformDashboard from '../pages/PlatformDashboard/PlatformDashboard';
import AgentChat from '../pages/AgentChat/AgentChat';
import ApprovalQueue from '../pages/ApprovalQueue/ApprovalQueue';
import AuditExplorer from '../pages/AuditExplorer/AuditExplorer';

import GatewayCenter from '../pages/GatewayCenter/GatewayCenter';
import GatewayRequests from '../pages/GatewayRequests/GatewayRequests';
import GatewayRequestDetail from '../pages/GatewayRequests/GatewayRequestDetail';
import Guardrails from '../pages/Guardrails/Guardrails';
import APIKeys from '../pages/APIKeys/APIKeys';
import Settings from '../pages/Settings/Settings';
import Login from '../pages/Login/Login';

const RoleHomeRedirect = () => {
  const { user } = useAuth();
  return <Navigate to={user?.role === 'Platform Admin' ? '/platform/dashboard' : '/chat'} replace />;
};

const AppRouter = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<RoleHomeRedirect />} />
        <Route path="platform" element={<Navigate to="/platform/dashboard" replace />} />
        <Route path="platform/dashboard" element={<PlatformDashboard />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="chat" element={<AgentChat />} />
        <Route path="policies" element={<Guardrails />} />
        <Route path="requests" element={<GatewayRequests />} />
        <Route path="approvals" element={<ApprovalQueue />} />
        <Route path="audit" element={<AuditExplorer />} />
        <Route path="providers" element={<GatewayCenter />} />
        <Route path="api-keys" element={<APIKeys />} />

        <Route path="gateway" element={<Navigate to="/providers" replace />} />
        <Route path="gateway/requests" element={<GatewayRequests />} />
        <Route path="gateway/requests/:requestId" element={<GatewayRequestDetail />} />
        <Route path="requests/:requestId" element={<GatewayRequestDetail />} />
        <Route path="guardrails" element={<Navigate to="/policies" replace />} />
        <Route path="settings" element={<Settings />} />

        <Route path="*" element={<RoleHomeRedirect />} />
      </Route>
    </Routes>
  );
};

export default AppRouter;

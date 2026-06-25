import apiClient from './api';

export const sendGatewayChatMessage = async (sessionId, message) => {
  const response = await apiClient.post('/gateway/chat', {
    session_id: sessionId,
    message,
  });
  return response.data;
};

export const getGatewayRequests = async (limit = 100) => {
  const response = await apiClient.get(`/gateway/requests?limit=${limit}`);
  return response.data;
};

export const getGatewayRequestById = async (requestId) => {
  const response = await apiClient.get(`/gateway/requests/${requestId}`);
  return response.data;
};

export const getGatewayApprovals = async () => {
  const response = await apiClient.get('/gateway/approvals');
  return response.data;
};

export const getGatewayStats = async () => {
  const [requests, approvals] = await Promise.all([
    getGatewayRequests(200),
    getGatewayApprovals(),
  ]);

  const providerUsage = requests.reduce((acc, req) => {
    const provider = req.provider || 'unknown';
    acc[provider] = (acc[provider] || 0) + 1;
    return acc;
  }, {});

  return {
    totalRequests: requests.length,
    approvedRequests: requests.filter((req) => req.status === 'allowed' || req.decision === 'ALLOW').length,
    blockedRequests: requests.filter((req) => req.status === 'blocked' || req.decision === 'BLOCK').length,
    pendingApprovals: approvals.filter((approval) => approval.status === 'pending').length,
    providerUsage,
    requests,
    approvals,
  };
};

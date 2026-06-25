import apiClient from './api';
import { getGatewayApprovals } from './gatewayService';

export const getApprovals = async () => {
  const response = await apiClient.get('/approvals');
  return response.data;
};

export const getApprovalsByMode = async (mode = 'gateway') => {
  if (mode === 'gateway') {
    return getGatewayApprovals();
  }
  return getApprovals();
};

export const getApprovalById = async (id) => {
  const response = await apiClient.get(`/approvals/${id}`);
  return response.data;
};

export const approveApproval = async (id, mfaCode = null) => {
  // If mfaCode is provided, send it in body, else empty string body for legacy compat
  const config = mfaCode 
    ? { headers: { 'Content-Type': 'application/json' } }
    : { headers: { 'Content-Type': 'text/plain' } };
  const payload = mfaCode ? { mfa_code: mfaCode } : "";
  const response = await apiClient.post(`/approve/${id}`, payload, config);
  return response.data;
};

export const rejectApproval = async (id) => {
  const response = await apiClient.post(`/reject/${id}`);
  return response.data;
};

export const executeApproval = async (id) => {
  const response = await apiClient.post(`/execute/${id}`);
  return response.data;
};

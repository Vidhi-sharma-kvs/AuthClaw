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

export const approveApproval = async (id, mfaCode = null, comment = '') => {
  const response = await apiClient.post(`/approve/${id}`, { mfa_code: mfaCode, comment });
  return response.data;
};

export const rejectApproval = async (id, comment = '') => {
  const response = await apiClient.post(`/reject/${id}`, { comment });
  return response.data;
};

export const executeApproval = async (id, mfaCode = null, comment = '') => {
  const response = await apiClient.post(`/execute/${id}`, { mfa_code: mfaCode, comment });
  return response.data;
};

import apiClient from './api';

export const getHashChain = async (limit = 50) => {
  const response = await apiClient.get(`/audit/hash-chain?limit=${limit}`);
  return response.data;
};

export const verifyAuditChain = async () => {
  const response = await apiClient.get('/audit/verify');
  return response.data;
};

export const getAuditSummary = async () => {
  const response = await apiClient.get('/audit/verify/summary');
  return response.data;
};

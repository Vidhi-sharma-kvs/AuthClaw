import apiClient from './api';

export const listRemediationConnectors = async () => {
  const response = await apiClient.get('/remediation/connectors');
  return response.data;
};

export const saveRemediationConnector = async (payload) => {
  const response = await apiClient.post('/remediation/connectors', payload);
  return response.data;
};

export const testRemediationConnector = async (connectorId) => {
  const response = await apiClient.post(`/remediation/connectors/${connectorId}/test`);
  return response.data;
};

export const runRemediationScan = async (connectorId) => {
  const response = await apiClient.post('/remediation/scans', { connector_id: connectorId });
  return response.data;
};

export const listRemediationFindings = async () => {
  const response = await apiClient.get('/remediation/findings');
  return response.data;
};

export const createRemediationPlan = async (findingId) => {
  const response = await apiClient.post(`/remediation/findings/${findingId}/plan`);
  return response.data;
};

export const requestRemediationApproval = async (planId) => {
  const response = await apiClient.post(`/remediation/plans/${planId}/approval`);
  return response.data;
};

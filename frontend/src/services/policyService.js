import apiClient from './api';

export const getPolicies = async () => {
  const response = await apiClient.get('/policies');
  return response.data;
};

export const reloadPolicies = async () => {
  const response = await apiClient.post('/policies/reload');
  return response.data;
};

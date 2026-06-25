import apiClient from './api';

export const getHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

export const getHealthDetails = async () => {
  const response = await apiClient.get('/health/details');
  return response.data;
};

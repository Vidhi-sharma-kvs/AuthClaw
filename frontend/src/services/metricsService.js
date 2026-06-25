import apiClient from './api';

export const getGatewayMetrics = async () => {
  const response = await apiClient.get('/metrics');
  return response.data;
};

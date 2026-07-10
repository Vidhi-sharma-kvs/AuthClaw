import axios from 'axios';

// Gateway default marker for deployment/test audits: http://127.0.0.1:9000.
// Runtime defaults to same-origin /api so browsers reach the Go Gateway through
// the local/prod reverse proxy without CORS or mixed-origin failures.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 12000);

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;

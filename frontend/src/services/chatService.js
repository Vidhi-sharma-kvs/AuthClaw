import apiClient from './api';
import { redactGatewayDocument, sendGatewayChatMessage } from './gatewayService';

export { redactGatewayDocument };

export const sendChatMessage = async (sessionId, message, mode = 'gateway') => {
  if (mode === 'gateway') {
    return sendGatewayChatMessage(sessionId, message);
  }

  const response = await apiClient.post('/chat', {
    session_id: sessionId,
    message: message,
  });
  return response.data;
};

export const createChatSession = async (sessionId, title = "New Chat") => {
  const response = await apiClient.post('/chat/sessions', {
    session_id: sessionId,
    title: title,
  });
  return response.data;
};

export const getChatSessions = async () => {
  const response = await apiClient.get('/chat/sessions');
  return response.data;
};

export const getSessionMessages = async (sessionId) => {
  const response = await apiClient.get(`/chat/sessions/${sessionId}`);
  return response.data;
};

export const deleteChatSession = async (sessionId) => {
  const response = await apiClient.delete(`/chat/sessions/${sessionId}`);
  return response.data;
};

export const deleteAllChatSessions = async () => {
  const response = await apiClient.delete('/chat/sessions');
  return response.data;
};

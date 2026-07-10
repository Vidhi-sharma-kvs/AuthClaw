import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import apiClient from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [mfaSessionId, setMfaSessionId] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  const refreshTimeoutRef = useRef(null);
  const refreshPromiseRef = useRef(null);
  const refreshAccessTokenRef = useRef(null);

  // Setup request interceptor to append JWT Bearer token
  useEffect(() => {
    const requestInterceptor = apiClient.interceptors.request.use(
      (config) => {
        if (accessToken) {
          config.headers['Authorization'] = `Bearer ${accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    return () => {
      apiClient.interceptors.request.eject(requestInterceptor);
    };
  }, [accessToken]);

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
      refreshTimeoutRef.current = null;
    }
  }, []);

  const logout = useCallback(() => {
    clearRefreshTimer();
    refreshPromiseRef.current = null;
    setUser(null);
    setAccessToken(null);
    setMfaSessionId(null);
    setIsAuthenticated(false);
    localStorage.removeItem('authclaw_refresh_token');
    localStorage.removeItem('authclaw_user');
  }, [clearRefreshTimer]);

  // Decodes JWT payload (non-secured frontend extract helper for expiry check)
  const decodeJwtPayload = (token) => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (e) {
      return null;
    }
  };

  const scheduleRefresh = useCallback((token) => {
    clearRefreshTimer();
    const payload = decodeJwtPayload(token);
    if (payload && payload.exp) {
      const expMs = payload.exp * 1000;
      const delay = expMs - Date.now() - 60000; // Refresh 1 minute before expiry
      refreshTimeoutRef.current = setTimeout(() => {
        refreshAccessTokenRef.current?.();
      }, Math.max(delay, 30000));
    }
  }, [clearRefreshTimer]);

  const refreshAccessToken = useCallback(async () => {
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }
    const token = localStorage.getItem('authclaw_refresh_token');
    if (!token) {
      logout();
      return null;
    }

    refreshPromiseRef.current = (async () => {
      const response = await apiClient.post('/auth/refresh', { refresh_token: token });
      const { access_token } = response.data;
      setAccessToken(access_token);
      scheduleRefresh(access_token);
      return access_token;
    })();

    try {
      return await refreshPromiseRef.current;
    } catch (e) {
      logout();
      return null;
    } finally {
      refreshPromiseRef.current = null;
    }
  }, [logout, scheduleRefresh]);

  useEffect(() => {
    refreshAccessTokenRef.current = refreshAccessToken;
  }, [refreshAccessToken]);

  const handleAuthSuccess = useCallback((data) => {
    const { access_token, refresh_token, user: userData } = data;
    setAccessToken(access_token);
    setUser(userData);
    setIsAuthenticated(true);
    setMfaSessionId(null);

    localStorage.setItem('authclaw_refresh_token', refresh_token);
    localStorage.setItem('authclaw_user', JSON.stringify(userData));
    scheduleRefresh(access_token);
  }, [scheduleRefresh]);

  // Check existing session on boot
  useEffect(() => {
    const initializeAuth = async () => {
      const savedUser = localStorage.getItem('authclaw_user');
      const savedRefreshToken = localStorage.getItem('authclaw_refresh_token');

      if (savedUser && savedRefreshToken) {
        setUser(JSON.parse(savedUser));
        const token = await refreshAccessToken();
        if (token) {
          setIsAuthenticated(true);
        }
      }
      setLoading(false);
    };

    initializeAuth();
    return clearRefreshTimer;
  }, [clearRefreshTimer, refreshAccessToken]);

  const login = async (username, password) => {
    try {
      const response = await apiClient.post('/auth/login', { username, password });
      if (response.data.mfa_required) {
        setMfaSessionId(response.data.session_id);
        return { mfaRequired: true };
      }
      if (response.data.access_token) {
        handleAuthSuccess(response.data);
        return { mfaRequired: false };
      }
      throw new Error(response.data?.detail || response.data?.message || 'Authentication response was incomplete.');
    } catch (e) {
      if (e.response?.data && (e.response.data.email_verified === false || e.response.data.domain_verified === false)) {
        const err = new Error(e.response.data.detail || 'Verification required.');
        err.data = e.response.data;
        throw err;
      }
      throw new Error(e.response?.data?.detail || e.response?.data?.message || e.message || 'Authentication failed.');
    }
  };

  const verifyOtp = async (code) => {
    if (!mfaSessionId) {
      throw new Error('No active authentication session.');
    }
    try {
      const response = await apiClient.post('/auth/verify-otp', {
        session_id: mfaSessionId,
        code
      });
      handleAuthSuccess(response.data);
      return response.data.user;
    } catch (e) {
      throw new Error(e.response?.data?.detail || 'Invalid OTP code.');
    }
  };

  const clearMfaSession = () => {
    setMfaSessionId(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        mfaSessionId,
        isAuthenticated,
        loading,
        login,
        verifyOtp,
        logout,
        clearMfaSession
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

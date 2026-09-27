import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiClient from '../api/apiClient';

/* ==========================================================================
   AuthContext — real JWT auth against POST /auth/login.
   Stores the token + decoded payload (role, employee_id, exp) in
   localStorage so a page refresh doesn't log the user out.
   ========================================================================== */

const AuthContext = createContext(null);

const TOKEN_KEY = 'skillsprint_token';

// JWTs are base64url — no verification here (that's the backend's job,
// every request still hits real endpoints that check the signature). This
// is purely so the UI knows which dashboard/role to render without an
// extra round trip.
function decodeJwtPayload(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join('')
    );
    return JSON.parse(json);
  } catch (e) {
    return null;
  }
}

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const payload = token ? decodeJwtPayload(token) : null;
  const isExpired = payload?.exp ? Date.now() >= payload.exp * 1000 : false;

  const clearAuth = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // On mount (or token change), verify the token is still valid by calling
  // /auth/me — also refreshes `user` with the latest DB state.
  useEffect(() => {
    let cancelled = false;

    const verify = async () => {
      if (!token || isExpired) {
        if (token && isExpired) clearAuth();
        setIsLoading(false);
        return;
      }
      try {
        const res = await apiClient.get('/auth/me');
        if (!cancelled) setUser(res.data);
      } catch (err) {
        if (!cancelled) clearAuth();
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    verify();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const login = useCallback(async (email, password) => {
    const res = await apiClient.post('/auth/login', { email, password });
    const { access_token, user: loggedInUser } = res.data;
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    setUser(loggedInUser);
    return loggedInUser;
  }, []);

  const logout = useCallback(() => {
    clearAuth();
  }, [clearAuth]);

  const value = {
    token,
    user,
    role: user?.role || payload?.role || null,
    employeeId: payload?.employee_id ?? null,
    isAuthenticated: !!token && !!user && !isExpired,
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
};

export default AuthContext;

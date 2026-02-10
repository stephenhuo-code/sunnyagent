/**
 * Authentication state management hook
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef, createElement, ReactNode } from 'react';
import { UserInfo, login as apiLogin, logout as apiLogout, getCurrentUser } from '../api/auth';

interface AuthContextType {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAdmin: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

// Global 401 handler - clears user state when session expires
let globalLogoutHandler: (() => void) | null = null;

export function setGlobalLogoutHandler(handler: () => void) {
  globalLogoutHandler = handler;
}

export function handleUnauthorized() {
  if (globalLogoutHandler) {
    globalLogoutHandler();
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const isCheckingRef = useRef(false);

  // Set up global logout handler
  useEffect(() => {
    setGlobalLogoutHandler(() => {
      setUser(null);
    });
    return () => {
      setGlobalLogoutHandler(() => {});
    };
  }, []);

  const checkAuth = useCallback(async () => {
    if (isCheckingRef.current) return;
    isCheckingRef.current = true;

    try {
      const userData = await getCurrentUser();
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
      isCheckingRef.current = false;
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await apiLogin(username, password);
    setUser(response.user);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    isAdmin: user?.role === 'admin',
    login,
    logout,
    checkAuth,
  };

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Re-export for convenience
export { AuthContext };
export type { AuthContextType };

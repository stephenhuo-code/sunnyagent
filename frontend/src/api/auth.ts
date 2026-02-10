/**
 * Authentication API client
 */

export interface UserInfo {
  id: string;
  username: string;
  role: 'admin' | 'user';
  status: 'active' | 'disabled';
  created_at: string;
}

export interface LoginResponse {
  user: UserInfo;
  message: string;
}

const API_BASE = '/api';

export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  return response.json();
}

export async function logout(): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Logout failed');
  }
}

export async function getCurrentUser(): Promise<UserInfo> {
  const response = await fetch(`${API_BASE}/auth/me`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Not authenticated');
  }

  return response.json();
}

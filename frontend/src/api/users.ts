/**
 * API client for user management (admin only)
 */

import { handleUnauthorized } from '../hooks/useAuth';

function checkUnauthorized(res: Response) {
  if (res.status === 401) {
    handleUnauthorized();
  }
}

export type UserRole = "admin" | "user";
export type UserStatus = "active" | "disabled";

export interface UserInfo {
  id: string;
  username: string;
  role: UserRole;
  status: UserStatus;
  created_at: string;
}

export interface UserCreate {
  username: string;
  password: string;
  role: UserRole;
}

export interface UserListResponse {
  users: UserInfo[];
}

/**
 * List all users (admin only)
 */
export async function listUsers(): Promise<UserInfo[]> {
  const res = await fetch("/api/users", {
    credentials: "include",
  });
  checkUnauthorized(res);
  if (!res.ok) {
    if (res.status === 403) {
      throw new Error("Access denied. Admin privileges required.");
    }
    throw new Error("Failed to list users");
  }
  const data: UserListResponse = await res.json();
  return data.users;
}

/**
 * Create a new user (admin only)
 */
export async function createUser(user: UserCreate): Promise<UserInfo> {
  const res = await fetch("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(user),
  });
  if (!res.ok) {
    if (res.status === 403) {
      throw new Error("Access denied. Admin privileges required.");
    }
    if (res.status === 400) {
      const error = await res.json();
      throw new Error(error.detail || "Failed to create user");
    }
    throw new Error("Failed to create user");
  }
  return res.json();
}

/**
 * Delete a user (admin only)
 */
export async function deleteUser(userId: string): Promise<void> {
  const res = await fetch(`/api/users/${userId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    if (res.status === 403) {
      throw new Error("Access denied. Admin privileges required.");
    }
    if (res.status === 400) {
      const error = await res.json();
      throw new Error(error.detail || "Failed to delete user");
    }
    if (res.status === 404) {
      throw new Error("User not found");
    }
    throw new Error("Failed to delete user");
  }
}

/**
 * Update user status (admin only)
 */
export async function updateUserStatus(
  userId: string,
  status: UserStatus
): Promise<UserInfo> {
  const res = await fetch(`/api/users/${userId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    if (res.status === 403) {
      throw new Error("Access denied. Admin privileges required.");
    }
    if (res.status === 400) {
      const error = await res.json();
      throw new Error(error.detail || "Failed to update user status");
    }
    if (res.status === 404) {
      throw new Error("User not found");
    }
    throw new Error("Failed to update user status");
  }
  return res.json();
}

/**
 * User management panel for administrators
 */

import { useState, useEffect, useCallback } from "react";
import {
  Users,
  UserPlus,
  Trash2,
  Shield,
  User,
  Check,
  X,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { UserForm } from "./UserForm";
import {
  listUsers,
  createUser,
  deleteUser,
  updateUserStatus,
  type UserInfo,
  type UserRole,
} from "../../api/users";
import { useAuth } from "../../hooks/useAuth";
import "./Admin.css";

export function UserManagement() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载用户失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleCreateUser = async (
    username: string,
    password: string,
    role: UserRole
  ) => {
    await createUser({ username, password, role });
    setShowCreateForm(false);
    loadUsers();
  };

  const handleDeleteUser = async (userId: string) => {
    setActionInProgress(userId);
    try {
      await deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除用户失败");
    } finally {
      setActionInProgress(null);
      setDeleteConfirmId(null);
    }
  };

  const handleToggleStatus = async (user: UserInfo) => {
    setActionInProgress(user.id);
    try {
      const newStatus = user.status === "active" ? "disabled" : "active";
      const updated = await updateUserStatus(user.id, newStatus);
      setUsers((prev) =>
        prev.map((u) => (u.id === user.id ? updated : u))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新用户失败");
    } finally {
      setActionInProgress(null);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  if (isLoading) {
    return (
      <div className="admin-loading">
        <Loader2 size={32} className="spin" />
        <span>加载用户中...</span>
      </div>
    );
  }

  return (
    <div className="user-management">
      <div className="admin-header">
        <div className="admin-title">
          <Users size={24} />
          <h1>用户管理</h1>
        </div>
        <button
          className="btn-primary"
          onClick={() => setShowCreateForm(true)}
        >
          <UserPlus size={18} />
          添加用户
        </button>
      </div>

      {error && (
        <div className="admin-error">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button onClick={() => setError(null)}>
            <X size={16} />
          </button>
        </div>
      )}

      <div className="user-table-container">
        <table className="user-table">
          <thead>
            <tr>
              <th>用户</th>
              <th>角色</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr
                key={user.id}
                className={user.status === "disabled" ? "disabled" : ""}
              >
                <td>
                  <div className="user-cell">
                    {user.role === "admin" ? (
                      <Shield size={18} className="role-icon admin" />
                    ) : (
                      <User size={18} className="role-icon" />
                    )}
                    <span className="username">{user.username}</span>
                    {user.id === currentUser?.id && (
                      <span className="you-badge">(你)</span>
                    )}
                  </div>
                </td>
                <td>
                  <span className={`role-badge ${user.role}`}>
                    {user.role === "admin" ? "管理员" : "用户"}
                  </span>
                </td>
                <td>
                  <span className={`status-badge ${user.status}`}>
                    {user.status === "active" ? "启用" : "禁用"}
                  </span>
                </td>
                <td className="date-cell">{formatDate(user.created_at)}</td>
                <td>
                  {user.id === currentUser?.id ? (
                    <span className="no-actions">-</span>
                  ) : (
                    <div className="action-buttons">
                      <button
                        className={`action-btn ${user.status === "active" ? "disable" : "enable"}`}
                        onClick={() => handleToggleStatus(user)}
                        disabled={actionInProgress === user.id}
                        title={
                          user.status === "active"
                            ? "禁用用户"
                            : "启用用户"
                        }
                      >
                        {actionInProgress === user.id ? (
                          <Loader2 size={16} className="spin" />
                        ) : user.status === "active" ? (
                          <X size={16} />
                        ) : (
                          <Check size={16} />
                        )}
                      </button>

                      {deleteConfirmId === user.id ? (
                        <div className="delete-confirm-inline">
                          <button
                            className="action-btn confirm-delete"
                            onClick={() => handleDeleteUser(user.id)}
                            disabled={actionInProgress === user.id}
                            title="确认删除"
                          >
                            {actionInProgress === user.id ? (
                              <Loader2 size={16} className="spin" />
                            ) : (
                              <Check size={16} />
                            )}
                          </button>
                          <button
                            className="action-btn cancel-delete"
                            onClick={() => setDeleteConfirmId(null)}
                            title="取消"
                          >
                            <X size={16} />
                          </button>
                        </div>
                      ) : (
                        <button
                          className="action-btn delete"
                          onClick={() => setDeleteConfirmId(user.id)}
                          disabled={actionInProgress === user.id}
                          title="删除用户"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreateForm && (
        <UserForm
          onSubmit={handleCreateUser}
          onCancel={() => setShowCreateForm(false)}
        />
      )}
    </div>
  );
}

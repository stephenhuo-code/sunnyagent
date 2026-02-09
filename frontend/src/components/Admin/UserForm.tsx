/**
 * Form for creating a new user
 */

import { useState } from "react";
import { UserPlus, X, Eye, EyeOff } from "lucide-react";
import type { UserRole } from "../../api/users";
import "./Admin.css";

interface UserFormProps {
  onSubmit: (username: string, password: string, role: UserRole) => Promise<void>;
  onCancel: () => void;
}

export function UserForm({ onSubmit, onCancel }: UserFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("user");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username.trim()) {
      setError("请输入用户名");
      return;
    }
    if (!password.trim()) {
      setError("请输入密码");
      return;
    }
    if (password.length < 6) {
      setError("密码至少需要6个字符");
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit(username.trim(), password, role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建用户失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="user-form-overlay" onClick={onCancel}>
      <div className="user-form-modal" onClick={(e) => e.stopPropagation()}>
        <div className="user-form-header">
          <h3>
            <UserPlus size={20} />
            创建新用户
          </h3>
          <button className="close-btn" onClick={onCancel}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="username">用户名</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              autoFocus
              disabled={isSubmitting}
            />
          </div>

          <div className="form-field">
            <label htmlFor="password">密码</label>
            <div className="password-input-wrapper">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                disabled={isSubmitting}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="role">角色</label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              disabled={isSubmitting}
            >
              <option value="user">用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="form-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={onCancel}
              disabled={isSubmitting}
            >
              取消
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? "创建中..." : "创建用户"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

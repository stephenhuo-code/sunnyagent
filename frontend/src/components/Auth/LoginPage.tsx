/**
 * Login page component
 */

import { useState, FormEvent } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { Loader2, LogIn, AlertCircle } from 'lucide-react';
import './LoginPage.css';

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-header">
          <div className="login-logo">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              {/* Sun rays */}
              <g stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="24" y1="4" x2="24" y2="10" />
                <line x1="24" y1="38" x2="24" y2="44" />
                <line x1="4" y1="24" x2="10" y2="24" />
                <line x1="38" y1="24" x2="44" y2="24" />
                <line x1="9.86" y1="9.86" x2="14.1" y2="14.1" />
                <line x1="33.9" y1="33.9" x2="38.14" y2="38.14" />
                <line x1="9.86" y1="38.14" x2="14.1" y2="33.9" />
                <line x1="33.9" y1="14.1" x2="38.14" y2="9.86" />
              </g>
              {/* Central circle with gradient */}
              <circle cx="24" cy="24" r="12" fill="currentColor" opacity="0.1" />
              <circle cx="24" cy="24" r="12" stroke="currentColor" strokeWidth="2" fill="none" />
              {/* AI brain/network pattern inside */}
              <circle cx="24" cy="21" r="2" fill="currentColor" />
              <circle cx="19" cy="26" r="1.5" fill="currentColor" />
              <circle cx="29" cy="26" r="1.5" fill="currentColor" />
              <path d="M24 23v2M22 25l-2 1M26 25l2 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
          <h1>Sunny Agent</h1>
          <p className="login-subtitle">登录以继续</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {error && (
            <div className="login-error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              required
              disabled={isLoading}
              autoComplete="username"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              required
              disabled={isLoading}
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="login-button" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 size={18} className="spin" />
                <span>登录中...</span>
              </>
            ) : (
              <>
                <LogIn size={18} />
                <span>登录</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

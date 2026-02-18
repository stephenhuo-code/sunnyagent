/**
 * Modal for creating a new project
 */

import { useState, useRef, useEffect } from 'react';
import { X, Loader2 } from 'lucide-react';
import './Projects.css';

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}

export function NewProjectModal({ isOpen, onClose, onCreate }: NewProjectModalProps) {
  const [name, setName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setName('');
      setError(null);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('项目名称不能为空');
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      await onCreate(trimmedName);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建项目失败');
    } finally {
      setIsCreating(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>新建项目</h3>
          <button className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label htmlFor="project-name">项目名称</label>
              <input
                ref={inputRef}
                id="project-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="输入项目名称"
                maxLength={100}
                disabled={isCreating}
              />
              {error && <div className="form-error">{error}</div>}
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={isCreating}>
              取消
            </button>
            <button type="submit" className="btn-primary" disabled={isCreating || !name.trim()}>
              {isCreating ? (
                <>
                  <Loader2 size={16} className="spin" />
                  创建中...
                </>
              ) : (
                '创建项目'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

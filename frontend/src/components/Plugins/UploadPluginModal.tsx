/**
 * Upload plugin modal - drag and drop ZIP file upload.
 */

import { useState, useCallback } from "react";
import { X, Upload, FileArchive, AlertCircle, CheckCircle } from "lucide-react";
import "./Plugins.css";

interface UploadPluginModalProps {
  onClose: () => void;
  onUploadSuccess?: () => void;
}

interface UploadState {
  status: "idle" | "uploading" | "success" | "error";
  progress: number;
  message: string | null;
  warnings: string[] | null;
}

export function UploadPluginModal({ onClose, onUploadSuccess }: UploadPluginModalProps) {
  const [dragOver, setDragOver] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>({
    status: "idle",
    progress: 0,
    message: null,
    warnings: null,
  });

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const uploadFile = useCallback(async (file: File) => {
    if (!file.name.endsWith(".zip")) {
      setUploadState({
        status: "error",
        progress: 0,
        message: "Only ZIP files are accepted",
        warnings: null,
      });
      return;
    }

    setUploadState({
      status: "uploading",
      progress: 0,
      message: "Uploading...",
      warnings: null,
    });

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/plugins/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.detail?.errors?.join(", ") ||
          error.detail ||
          "Upload failed"
        );
      }

      const result = await response.json();

      setUploadState({
        status: "success",
        progress: 100,
        message: `Plugin "${result.plugin.display_name}" uploaded successfully!`,
        warnings: result.warnings,
      });

      onUploadSuccess?.();

      // Auto-close after success
      setTimeout(() => {
        onClose();
      }, 2000);

    } catch (err) {
      setUploadState({
        status: "error",
        progress: 0,
        message: err instanceof Error ? err.message : "Upload failed",
        warnings: null,
      });
    }
  }, [onClose, onUploadSuccess]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  }, [uploadFile]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      uploadFile(files[0]);
    }
  }, [uploadFile]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div className="upload-plugin-modal-overlay" onClick={handleBackdropClick}>
      <div className="upload-plugin-modal">
        <div className="upload-plugin-header">
          <h2>Upload Plugin</h2>
          <button className="upload-plugin-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="upload-plugin-content">
          {uploadState.status === "idle" && (
            <>
              <div
                className={`upload-dropzone ${dragOver ? "drag-over" : ""}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <FileArchive size={48} />
                <p className="upload-dropzone-title">
                  Drag and drop your plugin ZIP file here
                </p>
                <p className="upload-dropzone-subtitle">
                  or click to browse
                </p>
                <input
                  type="file"
                  accept=".zip"
                  onChange={handleFileSelect}
                  className="upload-dropzone-input"
                />
              </div>

              <div className="upload-requirements">
                <h4>Plugin Requirements</h4>
                <ul>
                  <li>ZIP file containing an <code>AGENTS.md</code> (for agents) or <code>SKILL.md</code> (for skills)</li>
                  <li>Optional <code>skills/</code> subdirectory for agent-bundled skills</li>
                  <li>Maximum file size: 50MB</li>
                </ul>
              </div>
            </>
          )}

          {uploadState.status === "uploading" && (
            <div className="upload-progress">
              <Upload size={48} className="upload-icon spinning" />
              <p>Uploading and validating plugin...</p>
              <div className="upload-progress-bar">
                <div
                  className="upload-progress-fill"
                  style={{ width: `${uploadState.progress}%` }}
                />
              </div>
            </div>
          )}

          {uploadState.status === "success" && (
            <div className="upload-result success">
              <CheckCircle size={48} />
              <p>{uploadState.message}</p>
              {uploadState.warnings && uploadState.warnings.length > 0 && (
                <div className="upload-warnings">
                  <h4>Warnings:</h4>
                  <ul>
                    {uploadState.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {uploadState.status === "error" && (
            <div className="upload-result error">
              <AlertCircle size={48} />
              <p>{uploadState.message}</p>
              <button
                className="upload-retry-btn"
                onClick={() => setUploadState({
                  status: "idle",
                  progress: 0,
                  message: null,
                  warnings: null,
                })}
              >
                Try Again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

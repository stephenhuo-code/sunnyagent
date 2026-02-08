import { useState, useEffect } from "react";
import { X, Download, FileText, File, Loader } from "lucide-react";
import type { FileAttachment } from "../types";
import { getFileContent } from "../api/client";

interface FilePreviewPanelProps {
  file: FileAttachment | null;
  onClose: () => void;
}

const TEXT_EXTENSIONS = [".txt", ".md", ".json", ".csv"];

function isTextFile(filename: string): boolean {
  const ext = filename.toLowerCase().slice(filename.lastIndexOf("."));
  return TEXT_EXTENSIONS.includes(ext);
}

export default function FilePreviewPanel({ file, onClose }: FilePreviewPanelProps) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setContent(null);
      setError(null);
      return;
    }

    if (!isTextFile(file.filename)) {
      setContent(null);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    getFileContent(file.file_id)
      .then((data) => setContent(data.content))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [file]);

  if (!file) return null;

  return (
    <div className="file-preview-panel">
      <div className="preview-header">
        <FileText size={18} className="preview-header-icon" />
        <span className="preview-filename">{file.filename}</span>
        <button className="preview-close-btn" onClick={onClose}>
          <X size={18} />
        </button>
      </div>

      <div className="preview-content">
        {loading ? (
          <div className="preview-loading">
            <Loader size={24} className="spinning" />
            <span>Loading...</span>
          </div>
        ) : error ? (
          <div className="preview-error">
            <span>{error}</span>
          </div>
        ) : content !== null ? (
          <pre className="preview-text">{content}</pre>
        ) : (
          <div className="preview-unsupported">
            <File size={48} />
            <p>Preview not available for this file type</p>
          </div>
        )}
      </div>

      <div className="preview-footer">
        <a
          href={file.download_url}
          download={file.filename}
          className="preview-download-btn"
        >
          <Download size={16} />
          Download
        </a>
      </div>
    </div>
  );
}

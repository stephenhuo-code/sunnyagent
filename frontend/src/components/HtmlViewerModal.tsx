import { useState } from "react";
import { X, Download, ExternalLink, Loader2 } from "lucide-react";
import type { FileAttachment } from "../types";
import { fixFileUrl } from "../utils/url";

interface HtmlViewerModalProps {
  file: FileAttachment | null;
  onClose: () => void;
}

export default function HtmlViewerModal({ file, onClose }: HtmlViewerModalProps) {
  const [loading, setLoading] = useState(true);

  if (!file) return null;

  // Fix sandbox: prefix if present
  const iframeSrc = fixFileUrl(file.download_url);

  return (
    <div className="html-viewer-overlay" onClick={onClose}>
      <div className="html-viewer-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="html-viewer-header">
          <span className="html-viewer-title">{file.filename}</span>
          <div className="html-viewer-actions">
            <a
              href={iframeSrc}
              target="_blank"
              rel="noopener noreferrer"
              className="html-viewer-btn"
              title="在新标签页打开"
            >
              <ExternalLink size={18} />
            </a>
            <a
              href={iframeSrc}
              download={file.filename}
              className="html-viewer-btn"
              title="下载"
            >
              <Download size={18} />
            </a>
            <button className="html-viewer-btn" onClick={onClose} title="关闭">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="html-viewer-content">
          {loading && (
            <div className="html-viewer-loading">
              <Loader2 size={24} className="spinning" />
              <span>加载中...</span>
            </div>
          )}
          <iframe
            src={iframeSrc}
            className="html-viewer-iframe"
            title={file.filename}
            sandbox="allow-scripts allow-same-origin"
            onLoad={() => setLoading(false)}
          />
        </div>
      </div>
    </div>
  );
}

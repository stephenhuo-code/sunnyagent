import { FileText, FileJson, FileSpreadsheet, File } from "lucide-react";
import type { FileAttachment } from "../types";

interface FileCardProps {
  file: FileAttachment;
  onClick?: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(filename: string) {
  const ext = filename.toLowerCase().split(".").pop();
  switch (ext) {
    case "json":
      return FileJson;
    case "csv":
      return FileSpreadsheet;
    case "txt":
    case "md":
      return FileText;
    default:
      return File;
  }
}

export default function FileCard({ file, onClick }: FileCardProps) {
  const Icon = getFileIcon(file.filename);

  return (
    <div className="file-card" onClick={onClick}>
      <Icon size={20} className="file-card-icon" />
      <div className="file-card-info">
        <span className="file-card-name">{file.filename}</span>
        <span className="file-card-size">{formatSize(file.size)}</span>
      </div>
    </div>
  );
}

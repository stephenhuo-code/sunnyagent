import { useState } from "react";
import {
  Search,
  Lightbulb,
  GitBranch,
  Loader2,
  Check,
  X,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import Markdown from "react-markdown";
import type { ToolCall } from "../types";

interface ToolCallCardProps {
  toolCall: ToolCall;
}

const TOOL_CONFIG: Record<
  string,
  { icon: typeof Search; label: string; color: string }
> = {
  tavily_search: { icon: Search, label: "Web Search", color: "var(--tool-search)" },
  think_tool: { icon: Lightbulb, label: "Thinking", color: "var(--tool-think)" },
  task: { icon: GitBranch, label: "Sub-agent", color: "var(--tool-task)" },
};

function getToolDisplay(name: string) {
  return TOOL_CONFIG[name] ?? { icon: GitBranch, label: name, color: "var(--text-muted)" };
}

function formatArgs(name: string, args: Record<string, unknown>): string {
  if (name === "tavily_search") return String(args.query ?? "");
  if (name === "think_tool") return String(args.reflection ?? "").slice(0, 200);
  if (name === "task") return String(args.description ?? "").slice(0, 200);
  return JSON.stringify(args, null, 2).slice(0, 200);
}

export default function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { icon: Icon, label, color } = getToolDisplay(toolCall.name);

  const StatusIcon =
    toolCall.status === "running"
      ? Loader2
      : toolCall.status === "done"
        ? Check
        : X;

  return (
    <div className="tool-call-card" style={{ borderLeftColor: color }}>
      <div
        className="tool-call-header"
        onClick={() => toolCall.output && setExpanded(!expanded)}
      >
        <Icon size={16} style={{ color, flexShrink: 0 }} />
        <span className="tool-call-label">{label}</span>
        <span className="tool-call-summary">{formatArgs(toolCall.name, toolCall.args)}</span>
        <StatusIcon
          size={14}
          className={`tool-status ${toolCall.status}`}
        />
        {toolCall.output && (
          expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
        )}
      </div>
      {expanded && toolCall.output && (
        <div className="tool-call-output">
          <Markdown>{toolCall.output.slice(0, 3000)}</Markdown>
        </div>
      )}
    </div>
  );
}

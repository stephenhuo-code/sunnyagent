import { useState, useEffect } from "react";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";
import type { ThinkingState } from "../types";

interface ThinkingBubbleProps {
  thinking: ThinkingState;
}

export default function ThinkingBubble({ thinking }: ThinkingBubbleProps) {
  const [expanded, setExpanded] = useState(true);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Live timer while thinking is active
  useEffect(() => {
    if (!thinking.isThinking) return;
    const interval = setInterval(() => {
      setElapsedSeconds(
        Math.round((Date.now() - thinking.startTime) / 1000),
      );
    }, 1000);
    return () => clearInterval(interval);
  }, [thinking.isThinking, thinking.startTime]);

  // Auto-collapse when thinking finishes
  useEffect(() => {
    if (!thinking.isThinking) {
      setExpanded(false);
    }
  }, [thinking.isThinking]);

  // Don't render if no steps and thinking has finished
  if (!thinking.isThinking && thinking.steps.length === 0) {
    return null;
  }

  const displaySeconds = thinking.isThinking
    ? elapsedSeconds
    : thinking.durationSeconds;

  return (
    <div
      className={`thinking-bubble ${thinking.isThinking ? "active" : "collapsed"}`}
    >
      <div
        className="thinking-header"
        onClick={() => !thinking.isThinking && setExpanded(!expanded)}
      >
        <Brain
          size={16}
          className={`thinking-icon ${thinking.isThinking ? "pulsing" : ""}`}
        />
        {thinking.isThinking ? (
          <span className="thinking-label">
            思考中
            <span className="thinking-dots">
              <span>.</span>
              <span>.</span>
              <span>.</span>
            </span>
            {displaySeconds > 0 && (
              <span className="thinking-timer"> {displaySeconds}秒</span>
            )}
          </span>
        ) : (
          <span className="thinking-label clickable">
            已思考 {displaySeconds} 秒
          </span>
        )}
        {!thinking.isThinking &&
          (expanded ? (
            <ChevronDown size={14} className="thinking-chevron" />
          ) : (
            <ChevronRight size={14} className="thinking-chevron" />
          ))}
      </div>
      {expanded && thinking.steps.length > 0 && (
        <div className="thinking-content">
          {/* Display thinking steps only - response content shows in Layer 3 */}
          <div className="thinking-steps">
            {thinking.steps.map((step, i) => (
              <div key={i} className="thinking-step">
                {step}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

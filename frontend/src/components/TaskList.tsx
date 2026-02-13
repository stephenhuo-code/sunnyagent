import { useState, memo } from "react";
import { ChevronRight, ChevronDown, CheckCircle, Circle, Loader2, XCircle } from "lucide-react";
import ToolCallCard from "./ToolCallCard";
import type { Todo, SpawnedTask } from "../types";

interface TaskListProps {
  todos?: Todo[];
  spawnedTasks?: SpawnedTask[];
}

/**
 * TaskList - Displays task tree for agent/planning scenarios
 * Layer 2 of the three-layer display structure
 */
function TaskList({ todos, spawnedTasks }: TaskListProps) {
  // Track expanded state for each task
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());

  const toggleTask = (taskId: string) => {
    setExpandedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  // Render status icon for todo items
  const renderTodoStatus = (status: Todo["status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle size={16} className="task-icon completed" />;
      case "in_progress":
        return <Loader2 size={16} className="task-icon in-progress spinning" />;
      default:
        return <Circle size={16} className="task-icon pending" />;
    }
  };

  // Render status icon for spawned tasks
  const renderTaskStatus = (status: SpawnedTask["status"]) => {
    switch (status) {
      case "success":
        return <CheckCircle size={16} className="task-icon completed" />;
      case "error":
        return <XCircle size={16} className="task-icon error" />;
      default:
        return <Loader2 size={16} className="task-icon in-progress spinning" />;
    }
  };

  return (
    <div className="task-list">
      {/* Render Todo items (from planning mode) */}
      {todos && todos.length > 0 && (
        <div className="task-section">
          {todos.map((todo, index) => (
            <div key={`todo-${index}`} className={`task-item ${todo.status}`}>
              {renderTodoStatus(todo.status)}
              <span className="task-content">{todo.content}</span>
            </div>
          ))}
        </div>
      )}

      {/* Render SpawnedTask items (from agent mode) */}
      {spawnedTasks && spawnedTasks.length > 0 && (
        <div className="task-section">
          {spawnedTasks.map((task) => {
            const isExpanded = expandedTasks.has(task.task_id);
            const hasToolCalls = task.toolCalls && task.toolCalls.length > 0;

            return (
              <div key={task.task_id} className={`spawned-task ${task.status}`}>
                <div
                  className="spawned-task-header"
                  onClick={() => hasToolCalls && toggleTask(task.task_id)}
                  style={{ cursor: hasToolCalls ? "pointer" : "default" }}
                >
                  {hasToolCalls && (
                    <span className="expand-icon">
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </span>
                  )}
                  {renderTaskStatus(task.status)}
                  <span className="task-type">{task.subagent_type}</span>
                  <span className="task-description">{task.description}</span>
                  {task.duration_ms !== undefined && (
                    <span className="task-duration">{(task.duration_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>

                {/* Expanded tool calls */}
                {isExpanded && hasToolCalls && (
                  <div className="spawned-task-tools">
                    {task.toolCalls.map((tc) => (
                      <ToolCallCard key={tc.id} toolCall={tc} />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default memo(TaskList);

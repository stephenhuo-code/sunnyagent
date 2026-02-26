import { useState, memo } from "react";
import { ChevronRight, ChevronDown, CheckCircle, Circle, Loader2, XCircle, MinusCircle } from "lucide-react";
import ToolCallCard from "./ToolCallCard";
import SafeMarkdown from "./SafeMarkdown";
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
      case "failed":
        return <XCircle size={16} className="task-icon error" />;
      case "cancelled":
        return <MinusCircle size={16} className="task-icon cancelled" />;
      case "pending":
        return <Circle size={16} className="task-icon pending" />;
      case "running":
      default:
        return <Loader2 size={16} className="task-icon in-progress spinning" />;
    }
  };

  // Filter tasks: only show active tasks, completely hide cancelled tasks
  const activeTasks = spawnedTasks?.filter(task => task.status !== "cancelled") || [];

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

      {/* Render active SpawnedTask items (from agent mode) */}
      {activeTasks.length > 0 && (
        <div className="task-section">
          {activeTasks.map((task) => {
            const isExpanded = expandedTasks.has(task.task_id);
            const hasToolCalls = task.toolCalls && task.toolCalls.length > 0;
            const hasOutput = task.output && task.output.trim().length > 0;
            const hasTodos = task.todos && task.todos.length > 0;
            const isExpandable = hasToolCalls || hasOutput || hasTodos;

            return (
              <div key={task.task_id} className={`spawned-task ${task.status}`}>
                <div
                  className="spawned-task-header"
                  onClick={() => isExpandable && toggleTask(task.task_id)}
                  style={{ cursor: isExpandable ? "pointer" : "default" }}
                >
                  {isExpandable && (
                    <span className="expand-icon">
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </span>
                  )}
                  {renderTaskStatus(task.status)}
                  <span className="task-type">{task.subagent_type}</span>
                  {task.description && (
                    <span className="task-description">
                      {task.description.length > 30
                        ? task.description.slice(0, 30) + "..."
                        : task.description}
                    </span>
                  )}
                  {task.duration_ms !== undefined && (
                    <span className="task-duration">{(task.duration_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>

                {/* Task todos (agent internal task breakdown) */}
                {isExpanded && hasTodos && (
                  <div className="spawned-task-todos">
                    {task.todos!.map((todo, idx) => (
                      <div key={idx} className={`task-item ${todo.status}`}>
                        {renderTodoStatus(todo.status)}
                        <span className="task-content">{todo.content}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Task output (shown after todos) */}
                {isExpanded && hasOutput && (
                  <div className="task-output">
                    <SafeMarkdown>{task.output!}</SafeMarkdown>
                  </div>
                )}

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

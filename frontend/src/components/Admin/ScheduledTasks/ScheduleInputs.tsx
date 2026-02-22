/**
 * Schedule type specific input components for scheduled tasks.
 */

import type {
  ScheduleType,
  ScheduleConfig,
  OnceScheduleConfig,
  DailyScheduleConfig,
  WeeklyScheduleConfig,
  MonthlyScheduleConfig,
  DayOfWeek,
} from "../../../api/scheduledTasks";

interface ScheduleInputsProps {
  scheduleType: ScheduleType;
  scheduleConfig: ScheduleConfig;
  onChange: (config: ScheduleConfig) => void;
  disabled?: boolean;
}

const DAY_OF_WEEK_OPTIONS: { value: DayOfWeek; label: string }[] = [
  { value: "mon", label: "周一" },
  { value: "tue", label: "周二" },
  { value: "wed", label: "周三" },
  { value: "thu", label: "周四" },
  { value: "fri", label: "周五" },
  { value: "sat", label: "周六" },
  { value: "sun", label: "周日" },
];

export function ScheduleInputs({
  scheduleType,
  scheduleConfig,
  onChange,
  disabled = false,
}: ScheduleInputsProps) {
  switch (scheduleType) {
    case "once":
      return (
        <OnceScheduleInputs
          config={scheduleConfig as OnceScheduleConfig}
          onChange={onChange}
          disabled={disabled}
        />
      );
    case "daily":
      return (
        <DailyScheduleInputs
          config={scheduleConfig as DailyScheduleConfig}
          onChange={onChange}
          disabled={disabled}
        />
      );
    case "weekly":
      return (
        <WeeklyScheduleInputs
          config={scheduleConfig as WeeklyScheduleConfig}
          onChange={onChange}
          disabled={disabled}
        />
      );
    case "monthly":
      return (
        <MonthlyScheduleInputs
          config={scheduleConfig as MonthlyScheduleConfig}
          onChange={onChange}
          disabled={disabled}
        />
      );
    default:
      return null;
  }
}

interface OnceScheduleInputsProps {
  config: OnceScheduleConfig;
  onChange: (config: OnceScheduleConfig) => void;
  disabled: boolean;
}

function OnceScheduleInputs({
  config,
  onChange,
  disabled,
}: OnceScheduleInputsProps) {
  return (
    <div className="schedule-inputs">
      <div className="schedule-input-row">
        <div className="form-field">
          <label>执行日期</label>
          <input
            type="date"
            value={config.run_date}
            onChange={(e) => onChange({ ...config, run_date: e.target.value })}
            disabled={disabled}
            min={new Date().toISOString().split("T")[0]}
          />
        </div>
        <div className="form-field">
          <label>执行时间</label>
          <input
            type="time"
            value={config.run_time}
            onChange={(e) => onChange({ ...config, run_time: e.target.value })}
            disabled={disabled}
          />
        </div>
      </div>
    </div>
  );
}

interface DailyScheduleInputsProps {
  config: DailyScheduleConfig;
  onChange: (config: DailyScheduleConfig) => void;
  disabled: boolean;
}

function DailyScheduleInputs({
  config,
  onChange,
  disabled,
}: DailyScheduleInputsProps) {
  return (
    <div className="schedule-inputs">
      <div className="form-field">
        <label>每天执行时间</label>
        <input
          type="time"
          value={config.time}
          onChange={(e) => onChange({ ...config, time: e.target.value })}
          disabled={disabled}
        />
      </div>
    </div>
  );
}

interface WeeklyScheduleInputsProps {
  config: WeeklyScheduleConfig;
  onChange: (config: WeeklyScheduleConfig) => void;
  disabled: boolean;
}

function WeeklyScheduleInputs({
  config,
  onChange,
  disabled,
}: WeeklyScheduleInputsProps) {
  const toggleDay = (day: DayOfWeek) => {
    const days = config.days_of_week || [];
    const newDays = days.includes(day)
      ? days.filter((d) => d !== day)
      : [...days, day];
    onChange({ ...config, days_of_week: newDays });
  };

  return (
    <div className="schedule-inputs">
      <div className="form-field">
        <label>选择星期</label>
        <div className="day-selector">
          {DAY_OF_WEEK_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className={`day-btn ${config.days_of_week?.includes(value) ? "selected" : ""}`}
              onClick={() => toggleDay(value)}
              disabled={disabled}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="form-field">
        <label>执行时间</label>
        <input
          type="time"
          value={config.time}
          onChange={(e) => onChange({ ...config, time: e.target.value })}
          disabled={disabled}
        />
      </div>
    </div>
  );
}

interface MonthlyScheduleInputsProps {
  config: MonthlyScheduleConfig;
  onChange: (config: MonthlyScheduleConfig) => void;
  disabled: boolean;
}

function MonthlyScheduleInputs({
  config,
  onChange,
  disabled,
}: MonthlyScheduleInputsProps) {
  const toggleDay = (day: number) => {
    const days = config.days_of_month || [];
    const newDays = days.includes(day)
      ? days.filter((d) => d !== day)
      : [...days, day].sort((a, b) => a - b);
    onChange({ ...config, days_of_month: newDays });
  };

  return (
    <div className="schedule-inputs">
      <div className="form-field">
        <label>选择日期（每月）</label>
        <div className="month-day-selector">
          {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => (
            <button
              key={day}
              type="button"
              className={`month-day-btn ${config.days_of_month?.includes(day) ? "selected" : ""}`}
              onClick={() => toggleDay(day)}
              disabled={disabled}
            >
              {day}
            </button>
          ))}
        </div>
        <p className="input-hint">如果选择31日，在没有31日的月份会在最后一天执行</p>
      </div>
      <div className="form-field">
        <label>执行时间</label>
        <input
          type="time"
          value={config.time}
          onChange={(e) => onChange({ ...config, time: e.target.value })}
          disabled={disabled}
        />
      </div>
    </div>
  );
}

// Helper to create default config for each schedule type
export function getDefaultScheduleConfig(scheduleType: ScheduleType): ScheduleConfig {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const defaultDate = tomorrow.toISOString().split("T")[0];

  switch (scheduleType) {
    case "once":
      return { run_date: defaultDate, run_time: "09:00" };
    case "daily":
      return { time: "09:00" };
    case "weekly":
      return { days_of_week: ["mon"], time: "09:00" };
    case "monthly":
      return { days_of_month: [1], time: "09:00" };
    default:
      return { time: "09:00" };
  }
}

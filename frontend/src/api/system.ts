/**
 * System API - system settings and monitoring
 */

export type Granularity = "day" | "week" | "month";

export interface TimeUsage {
  date: string;
  tokens: number;
  cost: number;
  calls: number;
}

export interface ModelUsage {
  model: string;
  tokens: number;
  cost: number;
  calls: number;
}

export interface UserUsage {
  user_id: string;
  username: string;
  tokens: number;
  cost: number;
  calls: number;
}

export interface UsageStats {
  granularity: Granularity;
  period_days: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
  total_calls: number;
  by_time: TimeUsage[];
  by_model: ModelUsage[];
  by_user: UserUsage[];
  error?: string;
}

export interface LangfuseStatus {
  enabled: boolean;
  url: string;
  status: "healthy" | "unhealthy" | "disabled";
}

export async function getLangfuseStatus(): Promise<LangfuseStatus> {
  const response = await fetch("/api/system/langfuse", {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch Langfuse status");
  }
  return response.json();
}

export async function getUsageStats(
  granularity: Granularity = "day",
  days: number = 30,
  startDate?: string
): Promise<UsageStats> {
  const params = new URLSearchParams({
    granularity,
    days: days.toString(),
  });
  if (startDate) {
    params.append("start_date", startDate);
  }

  const response = await fetch(`/api/system/usage?${params}`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Failed to fetch usage statistics");
  }

  return response.json();
}

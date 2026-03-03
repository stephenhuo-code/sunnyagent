/**
 * API client for plugin management endpoints.
 */

import type {
  CommandDetail,
  MarketplaceParams,
  PluginInfo,
  PluginListParams,
  PluginListResponse,
  PluginRatingInfo,
  PluginRatingRequest,
  PluginStateUpdateRequest,
  PluginUploadResponse,
} from "../types/plugins";

const API_BASE = "/api";

// =============================================================================
// Helper Functions
// =============================================================================

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

function buildQueryString(params: Record<string, string | boolean | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      searchParams.append(key, String(value));
    }
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

// =============================================================================
// Plugin List APIs
// =============================================================================

/**
 * List all plugins visible to the current user.
 */
export async function listPlugins(params?: PluginListParams): Promise<PluginInfo[]> {
  const query = buildQueryString((params ?? {}) as Record<string, string | boolean | undefined>);
  const response = await fetchJSON<PluginListResponse>(`${API_BASE}/plugins${query}`);
  return response.plugins;
}

/**
 * Get details of a specific plugin.
 */
export async function getPlugin(pluginName: string): Promise<PluginInfo> {
  return fetchJSON<PluginInfo>(`${API_BASE}/plugins/${encodeURIComponent(pluginName)}`);
}

/**
 * Browse plugin marketplace (preset, package, shared).
 */
export async function browseMarketplace(params?: MarketplaceParams): Promise<PluginInfo[]> {
  const query = buildQueryString((params ?? {}) as Record<string, string | boolean | undefined>);
  const response = await fetchJSON<PluginListResponse>(`${API_BASE}/plugins/marketplace${query}`);
  return response.plugins;
}

// =============================================================================
// Plugin State APIs
// =============================================================================

/**
 * Update plugin enabled state for the current user.
 */
export async function updatePluginState(
  pluginName: string,
  request: PluginStateUpdateRequest
): Promise<PluginInfo> {
  return fetchJSON<PluginInfo>(`${API_BASE}/plugins/${encodeURIComponent(pluginName)}`, {
    method: "PATCH",
    body: JSON.stringify(request),
  });
}

// =============================================================================
// Plugin Upload APIs
// =============================================================================

/**
 * Upload a new plugin package (ZIP file).
 */
export async function uploadPlugin(file: File): Promise<PluginUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/plugins/upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Delete an uploaded plugin.
 */
export async function deletePlugin(pluginName: string): Promise<void> {
  const response = await fetch(`${API_BASE}/plugins/${encodeURIComponent(pluginName)}`, {
    method: "DELETE",
    credentials: "include",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

// =============================================================================
// Plugin Share APIs
// =============================================================================

/**
 * Share a plugin to the marketplace.
 */
export async function sharePlugin(pluginName: string): Promise<PluginInfo> {
  return fetchJSON<PluginInfo>(`${API_BASE}/plugins/${encodeURIComponent(pluginName)}/share`, {
    method: "POST",
  });
}

/**
 * Unshare a plugin from the marketplace.
 */
export async function unsharePlugin(pluginName: string): Promise<PluginInfo> {
  return fetchJSON<PluginInfo>(`${API_BASE}/plugins/${encodeURIComponent(pluginName)}/share`, {
    method: "DELETE",
  });
}

// =============================================================================
// Plugin Rating APIs
// =============================================================================

/**
 * Get rating summary for a plugin.
 */
export async function getPluginRating(pluginName: string): Promise<PluginRatingInfo> {
  return fetchJSON<PluginRatingInfo>(
    `${API_BASE}/plugins/${encodeURIComponent(pluginName)}/rating`
  );
}

/**
 * Rate a plugin (1-5 stars).
 */
export async function ratePlugin(
  pluginName: string,
  request: PluginRatingRequest
): Promise<PluginRatingInfo> {
  return fetchJSON<PluginRatingInfo>(
    `${API_BASE}/plugins/${encodeURIComponent(pluginName)}/rating`,
    {
      method: "PUT",
      body: JSON.stringify(request),
    }
  );
}

// =============================================================================
// Command Detail APIs
// =============================================================================

/**
 * Get detailed info for a specific command including workflow content.
 */
export async function getCommandDetail(name: string): Promise<CommandDetail> {
  return fetchJSON<CommandDetail>(`${API_BASE}/commands/${encodeURIComponent(name)}`);
}

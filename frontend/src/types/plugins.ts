/**
 * TypeScript types for plugin management.
 * Generated from specs/012-plugin-management/contracts/plugins-api.yaml
 */

// =============================================================================
// Enums
// =============================================================================

export type PluginSource = "preset" | "package" | "uploaded" | "shared";

export type PluginType = "agent" | "skill";

export type SkillType = "atomic" | "workflow";

// =============================================================================
// Nested Types
// =============================================================================

export interface SkillStepInfo {
  id: string;
  description: string;
  required_capability?: string;
}

export interface PluginRatingInfo {
  average: number;
  count: number;
}

// =============================================================================
// Main Types
// =============================================================================

export interface PluginInfo {
  // Core fields (required)
  name: string; // Namespaced format: {source}:{name}
  display_name: string;
  type: PluginType;
  source: PluginSource;
  description: string;
  version: string;
  enabled: boolean; // Current user's enabled state

  // Optional metadata
  author?: string;

  // Agent-specific fields
  capabilities?: string[];
  commands?: string[]; // /command list
  skills?: PluginInfo[]; // Nested skills for agents

  // Skill-specific fields
  skill_type?: SkillType;
  steps?: SkillStepInfo[];

  // Rating (Package/Shared only)
  rating?: PluginRatingInfo;

  // Upload/Share related
  uploader_id?: string;
  uploader_name?: string;
  is_delisted?: boolean;
}

// =============================================================================
// Request Types
// =============================================================================

export interface PluginStateUpdateRequest {
  enabled: boolean;
}

export interface PluginRatingRequest {
  rating: number; // 1-5
}

// =============================================================================
// Response Types
// =============================================================================

export interface PluginListResponse {
  plugins: PluginInfo[];
}

export interface PluginUploadResponse {
  plugin: PluginInfo;
  message: string;
}

// =============================================================================
// Query Parameters
// =============================================================================

export interface PluginListParams {
  source?: PluginSource;
  type?: PluginType;
  enabled?: boolean;
  search?: string;
}

export interface MarketplaceParams {
  source?: Exclude<PluginSource, "uploaded">;
  search?: string;
  sort?: "name" | "rating" | "recent";
}

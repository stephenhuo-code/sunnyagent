/**
 * URL utility functions for fixing and validating file URLs
 */

/**
 * Fix file URLs that may contain incorrect prefixes (e.g., sandbox:)
 */
export function fixFileUrl(url: string): string {
  if (!url) return url;

  // Fix sandbox: prefix that may be incorrectly added by agents
  if (url.startsWith("sandbox:")) {
    return url.replace("sandbox:", "");
  }

  return url;
}

/**
 * Check if a URL is potentially dangerous and should be blocked
 * Uses blacklist strategy: only reject known dangerous URL schemes
 */
export function isValidFileUrl(url: string): boolean {
  if (!url) return false;

  const fixed = fixFileUrl(url);
  const lowerUrl = fixed.toLowerCase().trim();

  // Blacklist: reject dangerous URL schemes
  const dangerousSchemes = ["javascript:", "data:", "vbscript:"];

  for (const scheme of dangerousSchemes) {
    if (lowerUrl.startsWith(scheme)) {
      return false;
    }
  }

  // Allow all other URLs (relative paths, http, https, /api/files/, etc.)
  return true;
}

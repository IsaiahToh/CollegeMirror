/**
 * API base URL configuration.
 *
 * In dev the Vite proxy forwards /examples, /generate, /jobs and /health to the
 * backend, so VITE_API_BASE_URL can stay unset. In production builds, set it to
 * the backend origin (e.g. https://api.example.com).
 */
export const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? "";

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

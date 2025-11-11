const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

function resolveBaseUrl(): string {
  if (configuredBaseUrl) {
    return configuredBaseUrl;
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    const defaultPort = protocol === "https:" ? "443" : "80";
    const configuredPort = import.meta.env.VITE_API_PORT?.trim() || "8080";
    const portSegment = configuredPort === defaultPort ? "" : `:${configuredPort}`;
    return `${protocol}//${hostname}${portSegment}`;
  }

  return "http://127.0.0.1:8080";
}

export const apiBaseUrl = resolveBaseUrl().replace(/\/$/, "");

export function resolveApiUrl(path: string): string {
  return `${apiBaseUrl}${path}`;
}
const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export const publicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export const internalApiBaseUrl =
  process.env.INTERNAL_API_BASE_URL ??
  process.env.API_PROXY_TARGET ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  DEFAULT_BACKEND_URL;

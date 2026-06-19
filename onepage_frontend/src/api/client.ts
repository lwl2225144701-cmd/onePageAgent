import axios, { AxiosHeaders } from "axios";
import type { UnifiedResponse } from "@/types/backend";

const anonymousIdKey = "onepage_anonymous_user_id";

function getAnonymousUserId() {
  if (typeof window === "undefined") return "server-render";
  const existing = localStorage.getItem(anonymousIdKey);
  if (existing) return existing;
  const next = crypto.randomUUID();
  localStorage.setItem(anonymousIdKey, next);
  return next;
}

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api",
  timeout: 30000
});

apiClient.interceptors.request.use((config) => {
  const headers = AxiosHeaders.from(config.headers);
  headers.set("X-Anonymous-User-Id", getAnonymousUserId());
  config.headers = headers;
  return config;
});

export async function unwrap<T>(request: Promise<{ data: UnifiedResponse<T> }>): Promise<T> {
  const response = await request;
  if (!response.data.success || response.data.data == null) {
    throw new Error(response.data.message ?? response.data.error_code ?? "Request failed");
  }
  return response.data.data;
}

export function createEventSource(path: string) {
  const userId = getAnonymousUserId();
  const baseURL = String(apiClient.defaults.baseURL ?? "/api");
  const base = /^https?:\/\//i.test(baseURL)
    ? baseURL
    : typeof window !== "undefined"
      ? `${window.location.origin}${baseURL.startsWith("/") ? baseURL : `/${baseURL}`}`
      : `http://localhost:3000${baseURL.startsWith("/") ? baseURL : `/${baseURL}`}`;
  const url = new URL(`${base.replace(/\/+$/, "")}${path}`);
  url.searchParams.set("anonymous_user_id", userId);
  return new EventSource(url.toString());
}

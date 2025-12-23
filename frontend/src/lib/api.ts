import { getInitData } from "./telegram";

const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const url = API_BASE ? `${API_BASE}${path}` : path;
  const initData = getInitData();

  const headers = new Headers(init?.headers || undefined);
  headers.set("Accept", "application/json");

  // Prefer header-based initData for GET requests.
  if (initData) {
    headers.set("X-Telegram-InitData", initData);
  }

  let body: BodyInit | undefined = init?.body as any;
  if (init && "json" in init) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json ?? {});
  }

  const res = await fetch(url, {
    method: init?.method || (init && "json" in init ? "POST" : "GET"),
    credentials: "include",
    headers,
    body,
  });

  const data = (await res.json().catch(() => null)) as any;
  if (!res.ok) {
    const msg = data && data.error ? String(data.error) : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data as T;
}

export const api = {
  authTelegram: () => {
    const initData = getInitData();
    return request<{ profile: any; actions: any[] }>("/api/auth/telegram", {
      method: "POST",
      json: { initData },
    });
  },
  me: () => request<{ profile: any; actions: any[] }>("/api/me"),
  menu: () => request<{ actions: any[] }>("/api/menu"),
  dictionaries: () => request<any>("/api/dictionaries"),
  stats: (period: "today" | "week" | "month") => request<any>(`/api/stats?period=${period}`),
  setName: (full_name: string) => request<any>("/api/profile/name", { method: "POST", json: { full_name } }),
  createReport: (payload: any) => request<any>("/api/report", { method: "POST", json: payload }),
  adminRoles: () => request<{ items: any[] }>("/api/admin/roles"),
  adminExport: () => request<any>("/api/admin/export", { method: "POST", json: {} }),
};

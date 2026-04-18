import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { Platform } from "react-native";

/**
 * В браузере на localhost запросы к 192.168.x.x часто «висят» (фаервол/маршрутизация).
 * Для веб-версии на ПК всегда бьём в тот же хост, что и бэкенд на машине разработчика.
 */
function resolveApiBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (Platform.OS === "web" && typeof window !== "undefined") {
    const h = window.location?.hostname;
    if (h === "localhost" || h === "127.0.0.1") {
      return "http://localhost:8000/api/v1";
    }
  }
  return fromEnv || "http://localhost:8000/api/v1";
}

const API_URL = resolveApiBaseUrl();

// Web-safe token storage
const tokenStorage = {
  async get(key: string): Promise<string | null> {
    if (Platform.OS === "web") return localStorage.getItem(key);
    const SecureStore = await import("expo-secure-store");
    return SecureStore.getItemAsync(key);
  },
  async set(key: string, value: string): Promise<void> {
    if (Platform.OS === "web") { localStorage.setItem(key, value); return; }
    const SecureStore = await import("expo-secure-store");
    return SecureStore.setItemAsync(key, value);
  },
  async delete(key: string): Promise<void> {
    if (Platform.OS === "web") { localStorage.removeItem(key); return; }
    const SecureStore = await import("expo-secure-store");
    return SecureStore.deleteItemAsync(key);
  },
};

export const api = axios.create({
  baseURL: resolveApiBaseUrl(),
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await tokenStorage.get("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      const refresh = await tokenStorage.get("refresh_token");
      if (refresh) {
        try {
          const base = resolveApiBaseUrl();
          const res = await axios.post(`${base}/auth/refresh`, { refresh_token: refresh });
          const { access_token, refresh_token } = res.data;
          await tokenStorage.set("access_token", access_token);
          await tokenStorage.set("refresh_token", refresh_token);
          if (error.config) {
            error.config.headers.Authorization = `Bearer ${access_token}`;
            return api.request(error.config);
          }
        } catch {
          await tokenStorage.delete("access_token");
          await tokenStorage.delete("refresh_token");
        }
      }
    }
    return Promise.reject(error);
  }
);

export const WS_URL = API_URL.replace(/^http/, "ws");

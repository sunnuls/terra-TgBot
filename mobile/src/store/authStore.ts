import { create } from "zustand";
import { Platform } from "react-native";
import { authApi } from "../api/auth";
import { api } from "../api/client";

// Web-safe secure storage: SecureStore on native, localStorage on web
const storage = {
  async getItem(key: string): Promise<string | null> {
    if (Platform.OS === "web") {
      return localStorage.getItem(key);
    }
    const SecureStore = await import("expo-secure-store");
    return SecureStore.getItemAsync(key);
  },
  async setItem(key: string, value: string): Promise<void> {
    if (Platform.OS === "web") {
      localStorage.setItem(key, value);
      return;
    }
    const SecureStore = await import("expo-secure-store");
    return SecureStore.setItemAsync(key, value);
  },
  async deleteItem(key: string): Promise<void> {
    if (Platform.OS === "web") {
      localStorage.removeItem(key);
      return;
    }
    const SecureStore = await import("expo-secure-store");
    return SecureStore.deleteItemAsync(key);
  },
};

interface User {
  id: number;
  full_name: string | null;
  username: string | null;
  phone: string | null;
  tz: string;
  role: string;
  is_active: boolean;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (login: string, password: string) => Promise<void>;
  register: (login: string, password: string, full_name: string) => Promise<void>;
  logout: () => Promise<void>;
  loadUser: () => Promise<void>;
  /** Refresh user data silently without showing a global loading spinner */
  refreshUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,

  loadUser: async () => {
    set({ isLoading: true });
    const token = await storage.getItem("access_token");
    if (!token) {
      set({ isLoading: false, isAuthenticated: false });
      return;
    }
    try {
      const res = await api.get("/users/me");
      set({ user: res.data, isAuthenticated: true, isLoading: false });
    } catch {
      await storage.deleteItem("access_token");
      await storage.deleteItem("refresh_token");
      set({ isLoading: false, isAuthenticated: false, user: null });
    }
  },

  login: async (login, password) => {
    const data = await authApi.login({ login, password });
    await storage.setItem("access_token", data.access_token);
    await storage.setItem("refresh_token", data.refresh_token);
    const res = await api.get("/users/me");
    set({ user: res.data, isAuthenticated: true, isLoading: false });
  },

  register: async (login, password, full_name) => {
    const data = await authApi.register({ login, password, full_name });
    await storage.setItem("access_token", data.access_token);
    await storage.setItem("refresh_token", data.refresh_token);
    const res = await api.get("/users/me");
    set({ user: res.data, isAuthenticated: true, isLoading: false });
  },

  refreshUser: async () => {
    try {
      const res = await api.get("/users/me");
      set({ user: res.data });
    } catch {
      // silently ignore — don't log out or show spinner
    }
  },

  logout: async () => {
    const refresh = await storage.getItem("refresh_token");
    if (refresh) await authApi.logout(refresh).catch(() => {});
    await storage.deleteItem("access_token");
    await storage.deleteItem("refresh_token");
    set({ user: null, isAuthenticated: false });
  },
}));

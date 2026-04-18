import { create } from "zustand";
import { api } from "../api/client";

interface User {
  id: number;
  full_name: string | null;
  username: string | null;
  role: string;
  is_active: boolean;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isLoading: boolean;
  login: (login: string, password: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: localStorage.getItem("access_token"),
  isLoading: true,

  loadUser: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) { set({ isLoading: false }); return; }
    try {
      const res = await api.get("/users/me");
      set({ user: res.data, isLoading: false });
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      set({ user: null, isLoading: false });
    }
  },

  login: async (login, password) => {
    const res = await api.post("/auth/login", { login, password });
    localStorage.setItem("access_token", res.data.access_token);
    localStorage.setItem("refresh_token", res.data.refresh_token);
    const me = await api.get("/users/me");
    set({ user: me.data, accessToken: res.data.access_token });
  },

  logout: () => {
    const refresh = localStorage.getItem("refresh_token");
    if (refresh) api.post("/auth/logout", { refresh_token: refresh }).catch(() => {});
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null });
  },
}));

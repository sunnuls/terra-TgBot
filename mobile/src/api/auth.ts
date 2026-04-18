import { api } from "./client";

export interface LoginPayload {
  login: string;
  password: string;
}

export interface RegisterPayload {
  login: string;
  password: string;
  full_name: string;
  phone?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: number;
  role: string;
}

export const authApi = {
  login: (data: LoginPayload) =>
    api.post<TokenResponse>("/auth/login", data).then((r) => r.data),

  register: (data: RegisterPayload) =>
    api.post<TokenResponse>("/auth/register", data).then((r) => r.data),

  refresh: (refresh_token: string) =>
    api.post<TokenResponse>("/auth/refresh", { refresh_token }).then((r) => r.data),

  logout: (refresh_token: string) =>
    api.post("/auth/logout", { refresh_token }),

  changePassword: (old_password: string, new_password: string) =>
    api.post("/auth/change-password", { old_password, new_password }),
};

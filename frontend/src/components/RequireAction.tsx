import React from "react";
import { Navigate } from "react-router-dom";
import { useAppState } from "../state/AppState";

export function RequireAction({ action, children }: { action: string; children: React.ReactNode }) {
  const { state } = useAppState();

  if (state.status === "loading" || state.status === "idle") {
    return <div className="container">Загрузка…</div>;
  }

  if (state.status === "error") {
    return <div className="container">Ошибка: {state.error}</div>;
  }

  if (!state.profile) {
    return <Navigate to="/" replace />;
  }

  const allowed = (state.actions || []).some((a) => a.action === action);
  if (!allowed) {
    return <div className="container">Нет доступа</div>;
  }

  return <>{children}</>;
}

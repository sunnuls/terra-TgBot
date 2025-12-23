import React from "react";
import { Navigate } from "react-router-dom";
import { Role, useAppState } from "../state/AppState";

export function ProtectedRoute({
  allow,
  children,
}: {
  allow?: Role[];
  children: React.ReactNode;
}) {
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

  if (allow && allow.length > 0) {
    if (!allow.includes(state.profile.role)) {
      return <div className="container">Нет доступа</div>;
    }
  }

  return <>{children}</>;
}

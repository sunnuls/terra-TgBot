import React, { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { api } from "./lib/api";
import { initTelegramUi } from "./lib/telegram";
import { PixelBackground } from "./scene/PixelBackground";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RequireAction } from "./components/RequireAction";
import { useAppState } from "./state/AppState";
import { HomePage } from "./pages/HomePage";
import { StatsPage } from "./pages/StatsPage";
import { AdminPage } from "./pages/AdminPage";
import { OtdPage } from "./pages/OtdPage";
import { SettingsPage } from "./pages/SettingsPage";
import { BrigadierPage } from "./pages/BrigadierPage";

export function App() {
  const { state, setLoading, setReady, setError } = useAppState();

  useEffect(() => {
    initTelegramUi();

    let cancelled = false;

    async function bootstrap() {
      try {
        setLoading();

        // 1) Try auth to establish cookie session (initData is sent in body)
        await api.authTelegram().catch(() => null);

        // 2) Fetch canonical profile
        const me = await api.me();
        // 3) Menu is data-driven from /api/menu
        const menu = await api.menu();
        if (cancelled) return;

        setReady(me.profile, (menu.actions || []) as any);
      } catch (e: any) {
        if (cancelled) return;
        setError(String(e?.message || e));
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [setError, setLoading, setReady]);

  return (
    <div className="appShell" style={{ position: "relative" }}>
      <PixelBackground />

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route
          path="/stats"
          element={
            <RequireAction action="stats">
              <StatsPage />
            </RequireAction>
          }
        />

        <Route
          path="/otd"
          element={
            <RequireAction action="otd">
              <OtdPage />
            </RequireAction>
          }
        />

        <Route
          path="/settings"
          element={
            <RequireAction action="settings">
              <SettingsPage />
            </RequireAction>
          }
        />

        <Route
          path="/brig"
          element={
            <RequireAction action="brig_report">
              <BrigadierPage />
            </RequireAction>
          }
        />

        <Route
          path="/admin"
          element={
            <RequireAction action="admin">
              <AdminPage />
            </RequireAction>
          }
        />
      </Routes>
    </div>
  );
}

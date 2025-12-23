import React from "react";
import { useAppState } from "../state/AppState";
import { PixelPanel } from "../ui/PixelPanel";
import { HeaderBar } from "../ui/HeaderBar";
import { PixelButton } from "../ui/PixelButton";
import { PixelIcon, PixelIconName } from "../ui/PixelIcon";
import { useNavigate } from "react-router-dom";

export function HomePage() {
  const { state } = useAppState();
  const nav = useNavigate();

  const role = state.profile?.role || "user";
  const fullName = state.profile?.full_name || "—";

  const frameStyle = (() => {
    try {
      const v = (localStorage.getItem("terra_frame") || "").toLowerCase();
      if (v === "farm") return "farm";
      return "steel";
    } catch {
      return "steel";
    }
  })();

  const iconForAction = (action: string): PixelIconName => {
    if (action === "otd") return "otd";
    if (action === "stats") return "stats";
    if (action === "settings") return "settings";
    if (action === "brig_report") return "brig";
    if (action === "admin") return "admin";
    return "otd";
  };

  const routeForAction = (action: string): string => {
    if (action === "otd") return "/otd";
    if (action === "stats") return "/stats";
    if (action === "settings") return "/settings";
    if (action === "brig_report") return "/brig";
    if (action === "admin") return "/admin";
    return "/";
  };

  return (
    <div className="pxScreen">
      <div className="container pxUI">
        <PixelPanel
          className={`pxPixelated pxPanel--glass pxPanel--${frameStyle} pxMainMenuFrame`.trim()}
        >
          <HeaderBar fullName={fullName} role={String(role)} balance={0} />
          <div className="pxDivider" />
          <div className="pxButtonList">
            {(state.actions || []).map((a) => (
              <div key={a.action}>
                <PixelButton
                  title={a.title}
                  subtitle={a.hint || a.action}
                  left={<PixelIcon name={iconForAction(a.action)} />}
                  onClick={() => nav(routeForAction(a.action))}
                />
              </div>
            ))}
          </div>
        </PixelPanel>
      </div>
    </div>
  );
}

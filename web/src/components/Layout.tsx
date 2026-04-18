import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Home,
  BookOpen,
  BarChart3,
  MessageSquare,
  Activity,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { useAuthStore } from "../store/authStore";

const NAV_ITEMS = [
  { path: "/", icon: Home, label: "Главная" },
  { path: "/feed", icon: Activity, label: "Лента отчётов" },
  { path: "/dictionaries", icon: BookOpen, label: "Справочники" },
  { path: "/reports", icon: BarChart3, label: "Отчёты и экспорт" },
  { path: "/chat", icon: MessageSquare, label: "Чаты" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  return (
    <div className="flex h-[100dvh] min-h-0 overflow-hidden">
      {/* Sidebar: z-index + touch targets — чтобы «Выйти» не перехватывался main на узких экранах */}
      <aside
        className={`${collapsed ? "w-16" : "w-64"} bg-primary-700 text-white flex flex-col transition-all duration-300 flex-shrink-0 min-h-0 relative z-20`}
      >
        <div className="flex items-center justify-between px-4 py-5 border-b border-primary-800 flex-shrink-0">
          {!collapsed && (
            <div>
              <div className="font-bold text-lg leading-tight">🌾 TerraApp</div>
              <div className="text-xs text-green-200 opacity-80">AdminPanel</div>
            </div>
          )}
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="p-2 -m-1 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-primary-800 transition-colors touch-manipulation"
            aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"}
          >
            {collapsed ? <Menu size={20} /> : <X size={20} />}
          </button>
        </div>

        <nav className="flex-1 py-4 overflow-y-auto">
          {NAV_ITEMS.map(({ path, icon: Icon, label }) => {
            const active = isActive(path);
            return (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-3 px-4 py-3 mx-2 rounded-lg transition-colors ${active ? "bg-white/20 font-semibold" : "hover:bg-white/10"}`}
              >
                <Icon size={18} className="flex-shrink-0" />
                {!collapsed && <span className="text-sm">{label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-primary-800 p-3 sm:p-4 flex-shrink-0 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          {!collapsed && (
            <div className="text-xs text-green-200 mb-2 sm:mb-3">
              <div className="font-semibold text-white truncate">{user?.full_name || "—"}</div>
              <div className="opacity-80 capitalize">{user?.role}</div>
            </div>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className={`flex items-center justify-center gap-2 text-green-200 hover:text-white active:text-white transition-colors text-sm w-full min-h-[48px] rounded-lg hover:bg-white/10 active:bg-white/15 touch-manipulation cursor-pointer ${collapsed ? "px-0" : "px-2"}`}
            aria-label="Выйти из аккаунта"
          >
            <LogOut size={18} className="flex-shrink-0" />
            {!collapsed && <span>Выйти</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 min-h-0 overflow-y-auto overflow-x-hidden bg-gray-50 flex flex-col relative z-0">
        {children}
      </main>
    </div>
  );
}

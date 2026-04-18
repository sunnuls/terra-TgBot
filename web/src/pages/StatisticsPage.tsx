import React, { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Users, ClipboardList, BarChart3, Clock, Search, X, Plus } from "lucide-react";
import { api } from "../api/client";
import { UserItem, RoleBadges, UserRoleEditor, parseRoles, ROLE_LABELS, ROLES } from "./UsersPage";

interface AdminStats {
  user_id: number;
  full_name: string | null;
  total_hours: number;
  report_count: number;
}

export default function StatisticsPage() {
  const navigate = useNavigate();
  const tableRef = useRef<HTMLDivElement>(null);
  const [showUsers, setShowUsers] = useState(false);
  const [editUser, setEditUser] = useState<UserItem | null>(null);
  const [userSearch, setUserSearch] = useState("");

  const today = new Date().toISOString().split("T")[0];
  const monthStart = today.slice(0, 8) + "01";

  const { data: stats = [] } = useQuery<AdminStats[]>({
    queryKey: ["admin-stats", monthStart, today],
    queryFn: () => api.get(`/export/stats/admin?date_from=${monthStart}&date_to=${today}`).then((r) => r.data),
  });

  const { data: users = [] } = useQuery<UserItem[]>({
    queryKey: ["users"],
    queryFn: () => api.get("/users?limit=500").then((r) => r.data),
  });

  const { data: onlineData } = useQuery<{ count: number }>({
    queryKey: ["online-count"],
    queryFn: () => api.get("/users/online-count").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const totalHours = stats.reduce((s, r) => s + r.total_hours, 0);
  const totalReports = stats.reduce((s, r) => s + r.report_count, 0);
  const onlineCount = onlineData?.count ?? 0;
  const totalUsers = users.length;

  const scrollToTable = () => {
    tableRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const filteredUsers = users.filter((u) =>
    !userSearch ||
    (u.full_name || "").toLowerCase().includes(userSearch.toLowerCase()) ||
    (u.username || "").toLowerCase().includes(userSearch.toLowerCase())
  );

  return (
    <div className="p-6 overflow-y-auto flex-1">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Статистика</h1>
        <p className="text-gray-500 text-sm mt-1">Текущий месяц — {new Date().toLocaleDateString("ru", { month: "long", year: "numeric" })}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<Clock className="text-primary-700" size={22} />}
          label="Всего часов"
          value={totalHours.toFixed(1)}
          color="bg-green-50"
          title="Открыть раздел «Отчёты и экспорт»"
          onClick={() => navigate("/reports")}
        />
        <StatCard
          icon={<ClipboardList className="text-blue-600" size={22} />}
          label="Отчётов"
          value={String(totalReports)}
          color="bg-blue-50"
          title="Открыть раздел «Отчёты и экспорт»"
          onClick={() => navigate("/reports")}
        />

        {/* Сотрудники — с зелёной лампочкой онлайн */}
        <button
          type="button"
          onClick={() => { setShowUsers(true); setUserSearch(""); }}
          title="Управление сотрудниками"
          className="card bg-purple-50 border-0 text-left w-full cursor-pointer transition-all hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-600 focus-visible:ring-offset-2"
        >
          <div className="flex items-center gap-3 mb-2">
            <Users className="text-purple-600" size={22} />
            <span className="text-sm text-gray-600 font-medium">Сотрудники</span>
          </div>
          <div className="flex items-end gap-3">
            <div className="text-3xl font-bold text-gray-900">{totalUsers || "—"}</div>
            <div className="flex items-center gap-1.5 pb-1">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
              </span>
              <span className="text-xs text-green-700 font-medium">{onlineCount} онлайн</span>
            </div>
          </div>
        </button>

        <StatCard
          icon={<BarChart3 className="text-orange-600" size={22} />}
          label="Ср. часов на чел."
          value={stats.filter((r) => r.report_count > 0).length ? (totalHours / stats.filter((r) => r.report_count > 0).length).toFixed(1) : "—"}
          color="bg-orange-50"
          title="Перейти к таблице сотрудников ниже"
          onClick={scrollToTable}
        />
      </div>

      <div ref={tableRef} id="stats-table" className="card scroll-mt-6">
        <h2 className="text-lg font-semibold mb-4">Топ сотрудников по часам</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-th">#</th>
                <th className="table-th">Имя</th>
                <th className="table-th text-right">Отчётов</th>
                <th className="table-th text-right">Часов</th>
              </tr>
            </thead>
            <tbody>
              {stats.slice(0, 20).map((row, idx) => (
                <tr key={row.user_id} className="hover:bg-gray-50">
                  <td className="table-td text-gray-400">{idx + 1}</td>
                  <td className="table-td font-medium">{row.full_name || `#${row.user_id}`}</td>
                  <td className="table-td text-right">{row.report_count}</td>
                  <td className="table-td text-right font-semibold text-primary-700">{row.total_hours.toFixed(1)}</td>
                </tr>
              ))}
              {stats.length === 0 && (
                <tr>
                  <td colSpan={4} className="table-td text-center text-gray-400 py-8">Нет данных за текущий месяц</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Users management panel */}
      {showUsers && (
        <div className="fixed inset-0 bg-black/50 z-50 flex justify-end" onClick={() => setShowUsers(false)}>
          <div
            className="bg-white h-full w-full max-w-xl shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Сотрудники</h2>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                  </span>
                  <span className="text-xs text-green-700">{onlineCount} онлайн</span>
                </div>
              </div>
              <button onClick={() => setShowUsers(false)} className="p-2 rounded-full hover:bg-gray-100">
                <X size={20} />
              </button>
            </div>

            {/* Search */}
            <div className="px-5 py-3 border-b border-gray-100">
              <div className="relative">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  className="input pl-9 w-full text-sm"
                  placeholder="Поиск по имени..."
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  autoFocus
                />
              </div>
            </div>

            {/* User list */}
            <div className="flex-1 overflow-y-auto">
              {filteredUsers.length === 0 ? (
                <div className="text-center text-gray-400 py-12 text-sm">Нет сотрудников</div>
              ) : (
                <ul>
                  {filteredUsers.map((u) => (
                    <li
                      key={u.id}
                      className="flex items-center gap-3 px-5 py-3.5 border-b border-gray-50 hover:bg-gray-50 transition-colors"
                    >
                      {/* Avatar placeholder */}
                      <div className="w-9 h-9 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center font-semibold text-sm flex-shrink-0">
                        {(u.full_name || u.username || "?")[0].toUpperCase()}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-900 text-sm truncate">
                          {u.full_name || u.username || `#${u.id}`}
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          <RoleBadges role={u.role} />
                        </div>
                      </div>

                      <button
                        className="flex-shrink-0 p-1.5 rounded-full border border-gray-200 hover:border-primary-500 hover:bg-primary-50 text-gray-400 hover:text-primary-600 transition-all"
                        onClick={() => setEditUser(u)}
                        title="Назначить роли"
                      >
                        <Plus size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {editUser && (
        <UserRoleEditor
          user={editUser}
          onClose={() => setEditUser(null)}
        />
      )}
    </div>
  );
}

function StatCard({
  icon, label, value, color, onClick, title,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
  onClick: () => void;
  title: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`card ${color} border-0 text-left w-full cursor-pointer transition-all hover:shadow-md hover:brightness-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-600 focus-visible:ring-offset-2 active:scale-[0.995]`}
    >
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-sm text-gray-600 font-medium">{label}</span>
      </div>
      <div className="text-3xl font-bold text-gray-900">{value}</div>
    </button>
  );
}

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { UserCheck, UserX, Edit2, Search, X, Check } from "lucide-react";
import { api } from "../api/client";
import { toast } from "../components/Toast";

export const ROLES = ["otd", "brigadier", "accountant", "admin"];
export const ROLE_LABELS: Record<string, string> = {
  otd: "ОТД",
  brigadier: "Бригадир",
  accountant: "Бухгалтер",
  admin: "Администратор",
  user: "Сотрудник",
  tim: "ТИМ",
  it: "IT",
};
export const ROLE_COLORS: Record<string, string> = {
  admin: "bg-red-100 text-red-700",
  accountant: "bg-yellow-100 text-yellow-700",
  brigadier: "bg-blue-100 text-blue-700",
  otd: "bg-green-100 text-green-700",
  it: "bg-purple-100 text-purple-700",
  tim: "bg-orange-100 text-orange-700",
  user: "bg-gray-100 text-gray-600",
};

export interface UserItem {
  id: number;
  full_name: string | null;
  username: string | null;
  phone: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export function parseRoles(role: string): string[] {
  return role.split(",").map((r) => r.trim()).filter(Boolean);
}

export function RoleBadges({ role }: { role: string }) {
  const roles = parseRoles(role);
  if (roles.length === 0 || (roles.length === 1 && roles[0] === "user")) {
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS["user"]}`}>
        Сотрудник
      </span>
    );
  }
  return (
    <div className="flex flex-wrap gap-1">
      {roles.map((r) => (
        <span key={r} className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[r] ?? "bg-gray-100 text-gray-600"}`}>
          {ROLE_LABELS[r] ?? r}
        </span>
      ))}
    </div>
  );
}

export function UserRoleEditor({
  user,
  onClose,
}: {
  user: UserItem;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const currentRoles = parseRoles(user.role);
  const [selected, setSelected] = useState<string[]>(
    currentRoles.filter((r) => ROLES.includes(r))
  );
  const [isActive, setIsActive] = useState(user.is_active);

  const toggle = (role: string) => {
    setSelected((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  const mutation = useMutation({
    mutationFn: () =>
      api.patch(`/users/${user.id}`, {
        role: selected.length > 0 ? selected.join(",") : "user",
        is_active: isActive,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      onClose();
      toast("success", "Роли обновлены");
    },
    onError: (e: any) => toast("error", e?.response?.data?.detail || "Ошибка"),
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">{user.full_name || user.username || `#${user.id}`}</h3>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100">
            <X size={20} />
          </button>
        </div>

        <p className="text-sm text-gray-500 mb-4">Выберите одну или несколько ролей:</p>

        <div className="grid grid-cols-2 gap-2 mb-5">
          {ROLES.map((role) => {
            const active = selected.includes(role);
            return (
              <button
                key={role}
                type="button"
                onClick={() => toggle(role)}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 text-sm font-medium transition-all ${
                  active
                    ? "border-primary-600 bg-primary-50 text-primary-700"
                    : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                }`}
              >
                <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 ${active ? "bg-primary-600" : "border-2 border-gray-300"}`}>
                  {active && <Check size={10} color="white" strokeWidth={3} />}
                </div>
                {ROLE_LABELS[role]}
              </button>
            );
          })}
        </div>

        <label className="flex items-center gap-2 cursor-pointer mb-5">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 accent-primary-700"
          />
          <span className="text-sm">Активный аккаунт</span>
        </label>

        <div className="flex gap-3">
          <button className="btn-secondary flex-1" onClick={onClose}>Отмена</button>
          <button
            className="btn-primary flex-1"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Сохранение..." : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function UsersPage() {
  const [search, setSearch] = useState("");
  const [editUser, setEditUser] = useState<UserItem | null>(null);

  const { data: users = [], isLoading } = useQuery<UserItem[]>({
    queryKey: ["users"],
    queryFn: () => api.get("/users?limit=500").then((r) => r.data),
  });

  const filtered = users.filter((u) =>
    !search ||
    (u.full_name || "").toLowerCase().includes(search.toLowerCase()) ||
    (u.username || "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Пользователи</h1>
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input pl-9 w-64"
            placeholder="Поиск..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-700" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="table-th">ID</th>
                  <th className="table-th">Имя</th>
                  <th className="table-th">Логин</th>
                  <th className="table-th">Телефон</th>
                  <th className="table-th">Роли</th>
                  <th className="table-th">Статус</th>
                  <th className="table-th">Регистрация</th>
                  <th className="table-th">Действия</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((user) => (
                  <tr key={user.id} className={`hover:bg-gray-50 ${!user.is_active ? "opacity-50" : ""}`}>
                    <td className="table-td text-gray-400 text-xs">{user.id}</td>
                    <td className="table-td font-medium">{user.full_name || "—"}</td>
                    <td className="table-td text-gray-500">{user.username || "—"}</td>
                    <td className="table-td">{user.phone || "—"}</td>
                    <td className="table-td"><RoleBadges role={user.role} /></td>
                    <td className="table-td">
                      {user.is_active
                        ? <span className="text-green-600 flex items-center gap-1 text-xs"><UserCheck size={12} />Активен</span>
                        : <span className="text-red-500 flex items-center gap-1 text-xs"><UserX size={12} />Неактивен</span>}
                    </td>
                    <td className="table-td text-xs text-gray-400">{new Date(user.created_at).toLocaleDateString("ru")}</td>
                    <td className="table-td">
                      <button
                        className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-primary-700 transition-colors"
                        onClick={() => setEditUser(user)}
                        title="Редактировать роли"
                      >
                        <Edit2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editUser && (
        <UserRoleEditor user={editUser} onClose={() => setEditUser(null)} />
      )}
    </div>
  );
}

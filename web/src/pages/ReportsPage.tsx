import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api } from "../api/client";
import { format, subDays } from "date-fns";

/** Соответствует ReportFeedItemOut: классика + flow «otd» */
interface OtdFeedRow {
  source: "otd" | "form";
  id: number;
  created_at: string;
  user_id: number | null;
  reg_name: string | null;
  work_date: string | null;
  hours: number | null;
  location: string | null;
  activity: string | null;
  activity_grp: string | null;
  machine_type: string | null;
  machine_name: string | null;
  crop: string | null;
  form_title: string | null;
}

export default function ReportsPage() {
  const today = format(new Date(), "yyyy-MM-dd");
  const [dateFrom, setDateFrom] = useState(format(subDays(new Date(), 7), "yyyy-MM-dd"));
  const [dateTo, setDateTo] = useState(today);
  const [search, setSearch] = useState("");

  const { data: reports = [], isLoading } = useQuery<OtdFeedRow[]>({
    queryKey: ["admin-otd-feed", dateFrom, dateTo],
    queryFn: () =>
      api
        .get<OtdFeedRow[]>("/admin/otd-feed", {
          params: { date_from: dateFrom, date_to: dateTo, limit: 2000 },
        })
        .then((r) => r.data),
  });

  const filtered = useMemo(
    () =>
      reports.filter((r) => {
        if (!search.trim()) return true;
        const q = search.toLowerCase();
        return (
          (r.reg_name || "").toLowerCase().includes(q) ||
          (r.activity || "").toLowerCase().includes(q) ||
          (r.location || "").toLowerCase().includes(q) ||
          (r.form_title || "").toLowerCase().includes(q)
        );
      }),
    [reports, search]
  );

  const totalHours = filtered.reduce((s, r) => s + (r.hours || 0), 0);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Отчёты ОТД</h1>
      </div>

      <div className="card mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">От</label>
            <input type="date" className="input" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">До</label>
            <input type="date" className="input" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-gray-500 mb-1">Поиск</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input className="input pl-8" placeholder="Имя, деятельность, поле, форма..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
          </div>
          <div className="text-sm text-gray-500">
            <span className="font-semibold text-primary-700">{filtered.length}</span> отчётов,
            <span className="font-semibold text-primary-700 ml-1">{totalHours.toFixed(1)}</span> часов
          </div>
        </div>
      </div>

      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-700" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="table-th">Источник</th>
                  <th className="table-th">ID</th>
                  <th className="table-th">Сотрудник</th>
                  <th className="table-th">Дата</th>
                  <th className="table-th">Часы</th>
                  <th className="table-th">Тип</th>
                  <th className="table-th">Деятельность</th>
                  <th className="table-th">Место</th>
                  <th className="table-th">Техника</th>
                  <th className="table-th">Культура</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={`${r.source}-${r.id}`} className="hover:bg-gray-50">
                    <td className="table-td text-xs text-gray-500">
                      {r.source === "form" ? (r.form_title || "Форма") : "ОТД"}
                    </td>
                    <td className="table-td text-xs text-gray-400">{r.id}</td>
                    <td className="table-td font-medium">{r.reg_name || `#${r.user_id}`}</td>
                    <td className="table-td">{r.work_date ?? "—"}</td>
                    <td className="table-td font-semibold text-primary-700">{r.hours ?? "—"}</td>
                    <td className="table-td">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${r.activity_grp === "техника" ? "bg-blue-50 text-blue-600" : "bg-orange-50 text-orange-600"}`}>
                        {r.activity_grp === "техника" ? "Техника" : "Ручная"}
                      </span>
                    </td>
                    <td className="table-td">{r.activity || "—"}</td>
                    <td className="table-td">{r.location || "—"}</td>
                    <td className="table-td text-xs text-gray-500">
                      {r.machine_type ? `${r.machine_type}${r.machine_name ? ` — ${r.machine_name}` : ""}` : "—"}
                    </td>
                    <td className="table-td">{r.crop || "—"}</td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={10} className="table-td text-center text-gray-400 py-8">Нет отчётов</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

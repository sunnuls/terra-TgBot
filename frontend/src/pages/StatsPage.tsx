import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

export function StatsPage() {
  const [period, setPeriod] = useState<"today" | "week" | "month">("week");
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    setErr("");

    api
      .stats(period)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e?.message || e));
      });

    return () => {
      cancelled = true;
    };
  }, [period]);

  return (
    <div className="container">
      <div className="card">
        <div style={{ fontWeight: 700 }}>Статистика</div>
        <div style={{ marginTop: 10 }} className="row">
          <button className="button" onClick={() => setPeriod("today")}>
            Сегодня
          </button>
          <button className="button" onClick={() => setPeriod("week")}>
            Неделя
          </button>
          <button className="button" onClick={() => setPeriod("month")}>
            Месяц
          </button>
        </div>

        <div style={{ height: 12 }} />

        {err ? (
          <div>Ошибка: {err}</div>
        ) : data ? (
          <div style={{ fontSize: 14 }}>
            <div>Период: {data.period}</div>
            <div>
              Даты: {data.range?.start} — {data.range?.end}
            </div>
            <div>Часы: {data.total_hours}</div>
          </div>
        ) : (
          <div>Загрузка…</div>
        )}
      </div>
    </div>
  );
}

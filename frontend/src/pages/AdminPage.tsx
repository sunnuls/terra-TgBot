import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

export function AdminPage() {
  const [roles, setRoles] = useState<any[]>([]);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    setErr("");

    api
      .adminRoles()
      .then((d) => {
        if (!cancelled) setRoles(d.items || []);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e?.message || e));
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const runExport = async () => {
    try {
      setErr("");
      await api.adminExport();
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  };

  return (
    <div className="container">
      <div className="card">
        <div style={{ fontWeight: 700 }}>Админ</div>
        {err ? <div style={{ marginTop: 8 }}>Ошибка: {err}</div> : null}

        <div style={{ marginTop: 12 }}>
          <button className="button" onClick={runExport} type="button">
            Экспорт (заглушка)
          </button>
        </div>

        <div style={{ height: 12 }} />

        <div style={{ fontWeight: 650 }}>Роли</div>
        <div style={{ marginTop: 8, fontSize: 13 }}>
          {roles.length === 0 ? (
            <div>—</div>
          ) : (
            roles.map((r, idx) => (
              <div key={idx}>
                {r.role}: {r.user_id}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

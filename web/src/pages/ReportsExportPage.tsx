import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ReportsPage from "./ReportsPage";
import ExportPage from "./ExportPage";

type Tab = "reports" | "export";

export default function ReportsExportPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get("tab") === "export" ? "export" : "reports";
  const [tab, setTab] = useState<Tab>(tabFromUrl);

  useEffect(() => {
    setTab(tabFromUrl);
  }, [tabFromUrl]);

  const setTabAndUrl = (t: Tab) => {
    setTab(t);
    if (t === "export") setSearchParams({ tab: "export" });
    else setSearchParams({});
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-6 pt-4">
        <div className="flex gap-1 mb-0">
          <button
            type="button"
            onClick={() => setTabAndUrl("reports")}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
              tab === "reports" ? "bg-gray-50 text-primary-800 border border-b-0 border-gray-200" : "text-gray-500 hover:text-gray-800"
            }`}
          >
            Отчёты
          </button>
          <button
            type="button"
            onClick={() => setTabAndUrl("export")}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
              tab === "export" ? "bg-gray-50 text-primary-800 border border-b-0 border-gray-200" : "text-gray-500 hover:text-gray-800"
            }`}
          >
            Экспорт
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden flex flex-col">
        {tab === "reports" ? <ReportsPage /> : <ExportPage />}
      </div>
    </div>
  );
}

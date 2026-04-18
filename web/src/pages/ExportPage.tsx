import React, { useState } from "react";
import { Download, FileSpreadsheet, BarChart3 } from "lucide-react";
import { api } from "../api/client";
import { format, subDays, startOfMonth } from "date-fns";

export default function ExportPage() {
  const today = format(new Date(), "yyyy-MM-dd");
  const [otdFrom, setOtdFrom] = useState(format(startOfMonth(new Date()), "yyyy-MM-dd"));
  const [otdTo, setOtdTo] = useState(today);
  const [accFrom, setAccFrom] = useState(format(startOfMonth(new Date()), "yyyy-MM-dd"));
  const [accTo, setAccTo] = useState(today);
  const [otdLoading, setOtdLoading] = useState(false);
  const [accLoading, setAccLoading] = useState(false);
  const [error, setError] = useState("");

  const downloadFile = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const handleOtdExport = async () => {
    setOtdLoading(true); setError("");
    try {
      const res = await api.post(`/export/excel/otd?date_from=${otdFrom}&date_to=${otdTo}`, {}, { responseType: "blob" });
      downloadFile(res.data, `ОТД_${otdFrom}_${otdTo}.xlsx`);
    } catch (e: any) {
      setError("Ошибка экспорта ОТД");
    } finally {
      setOtdLoading(false);
    }
  };

  const handleAccExport = async () => {
    setAccLoading(true); setError("");
    try {
      const res = await api.post(`/export/excel/accounting?date_from=${accFrom}&date_to=${accTo}`, {}, { responseType: "blob" });
      downloadFile(res.data, `ЗП-ОТД_${accFrom}_${accTo}.xlsx`);
    } catch (e: any) {
      setError("Ошибка экспорта ЗП");
    } finally {
      setAccLoading(false);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Экспорт данных</h1>

      {error && <div className="bg-red-50 text-red-600 border border-red-200 rounded-lg p-3 mb-4 text-sm">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* OTD Export */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-blue-50 rounded-lg"><FileSpreadsheet size={22} className="text-blue-600" /></div>
            <div>
              <h3 className="font-semibold">Отчёт ОТД</h3>
              <p className="text-xs text-gray-500">Excel со всеми рабочими отчётами</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">От</label>
              <input type="date" className="input" value={otdFrom} onChange={(e) => setOtdFrom(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">До</label>
              <input type="date" className="input" value={otdTo} onChange={(e) => setOtdTo(e.target.value)} />
            </div>
          </div>

          <button className="btn-primary w-full flex items-center justify-center gap-2" onClick={handleOtdExport} disabled={otdLoading}>
            <Download size={16} />
            {otdLoading ? "Загрузка..." : "Скачать ОТД.xlsx"}
          </button>
        </div>

        {/* Accounting Export */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-green-50 rounded-lg"><BarChart3 size={22} className="text-green-600" /></div>
            <div>
              <h3 className="font-semibold">Бухгалтерский отчёт ЗП-ОТД</h3>
              <p className="text-xs text-gray-500">Итого часов по каждому сотруднику</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">От</label>
              <input type="date" className="input" value={accFrom} onChange={(e) => setAccFrom(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">До</label>
              <input type="date" className="input" value={accTo} onChange={(e) => setAccTo(e.target.value)} />
            </div>
          </div>

          <button className="btn-primary w-full flex items-center justify-center gap-2" onClick={handleAccExport} disabled={accLoading}>
            <Download size={16} />
            {accLoading ? "Загрузка..." : "Скачать ЗП-ОТД.xlsx"}
          </button>
        </div>
      </div>

      <div className="card mt-6">
        <h3 className="font-semibold mb-2">Автоматический экспорт</h3>
        <p className="text-sm text-gray-500">
          Каждый день в 02:00 система автоматически формирует Excel-отчёт за прошедший день
          и сохраняет его на сервере в <code className="bg-gray-100 px-1 rounded">/tmp/terra_exports/</code>.
        </p>
      </div>
    </div>
  );
}

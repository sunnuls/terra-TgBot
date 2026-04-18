import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { BarChart3, Link2, Copy, X } from "lucide-react";
import { api } from "../api/client";

interface CompanyProfile {
  company_name: string;
}

interface InviteLinkOut {
  id: number;
  token: string;
  company_name: string;
  is_permanent: boolean;
  expires_at: string | null;
  max_visits: number | null;
  join_url: string;
}

function fullInviteUrl(joinUrl: string): string {
  if (joinUrl.startsWith("http://") || joinUrl.startsWith("https://")) return joinUrl;
  return `${window.location.origin}${joinUrl.startsWith("/") ? "" : "/"}${joinUrl}`;
}

export default function HomePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [created, setCreated] = useState<InviteLinkOut | null>(null);
  const [copyOk, setCopyOk] = useState(false);

  const { data: profile } = useQuery<CompanyProfile>({
    queryKey: ["company-profile"],
    queryFn: () => api.get("/admin/company").then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: {
      company_name: string;
      is_permanent: boolean;
      duration_hours: number | null;
      max_visits: number | null;
    }) => api.post<InviteLinkOut>("/admin/invite-links", body).then((r) => r.data),
    onSuccess: (data) => {
      setCreated(data);
      qc.invalidateQueries({ queryKey: ["company-profile"] });
    },
  });

  return (
    <div className="p-6 overflow-y-auto flex-1 flex flex-col items-center justify-center min-h-0">
      <div className="w-full max-w-lg text-center space-y-8">
        <div>
          <p className="text-sm text-gray-500 mb-1">Компания / организация</p>
          <h1 className="text-3xl md:text-4xl font-bold text-primary-800 tracking-tight">
            {profile?.company_name?.trim() ? profile.company_name : "— укажите при создании ссылки —"}
          </h1>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <button
            type="button"
            onClick={() => navigate("/statistics")}
            className="btn-primary flex items-center justify-center gap-2 py-4 px-8 text-base rounded-xl shadow-lg"
          >
            <BarChart3 size={22} />
            Статистика
          </button>
          <button
            type="button"
            onClick={() => {
              setModalOpen(true);
              setCreated(null);
              createMutation.reset();
            }}
            className="flex items-center justify-center gap-2 py-4 px-8 text-base rounded-xl border-2 border-primary-700 text-primary-800 font-semibold hover:bg-primary-50 transition-colors"
          >
            <Link2 size={22} />
            Создать ссылку
          </button>
        </div>
      </div>

      {modalOpen && (
        <InviteModal
          onClose={() => setModalOpen(false)}
          onSubmit={(body) => createMutation.mutate(body)}
          loading={createMutation.isPending}
          error={createMutation.error as Error | undefined}
          created={created}
          onCopy={() => {
            if (!created) return;
            const url = fullInviteUrl(created.join_url);
            void navigator.clipboard.writeText(url).then(() => {
              setCopyOk(true);
              setTimeout(() => setCopyOk(false), 2000);
            });
          }}
          copyOk={copyOk}
        />
      )}
    </div>
  );
}

function InviteModal({
  onClose,
  onSubmit,
  loading,
  error,
  created,
  onCopy,
  copyOk,
}: {
  onClose: () => void;
  onSubmit: (body: {
    company_name: string;
    is_permanent: boolean;
    duration_hours: number | null;
    max_visits: number | null;
  }) => void;
  loading: boolean;
  error?: Error;
  created: InviteLinkOut | null;
  onCopy: () => void;
  copyOk: boolean;
}) {
  const [companyName, setCompanyName] = useState("");
  const [permanent, setPermanent] = useState(true);
  const [durationHours, setDurationHours] = useState(24);
  const [maxVisits, setMaxVisits] = useState<string>("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const max = maxVisits.trim() === "" ? null : parseInt(maxVisits, 10);
    if (max !== null && (Number.isNaN(max) || max < 1)) return;
    onSubmit({
      company_name: companyName.trim(),
      is_permanent: permanent,
      duration_hours: permanent ? null : durationHours,
      max_visits: max,
    });
  };

  if (created) {
    const url = fullInviteUrl(created.join_url);
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
        <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 relative">
          <button type="button" className="absolute top-4 right-4 text-gray-400 hover:text-gray-600" onClick={onClose}>
            <X size={20} />
          </button>
          <h2 className="text-lg font-semibold mb-2">Ссылка создана</h2>
          <p className="text-sm text-gray-500 mb-4">Скопируйте и отправьте сотрудникам.</p>
          <div className="flex gap-2 items-stretch">
            <input readOnly className="input flex-1 text-sm" value={url} />
            <button type="button" className="btn-primary px-4 flex items-center gap-2 shrink-0" onClick={onCopy}>
              <Copy size={16} />
              {copyOk ? "Скопировано" : "Копировать"}
            </button>
          </div>
          <button type="button" className="mt-4 text-sm text-primary-700 hover:underline w-full" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 relative max-h-[90vh] overflow-y-auto">
        <button type="button" className="absolute top-4 right-4 text-gray-400 hover:text-gray-600" onClick={onClose}>
          <X size={20} />
        </button>
        <h2 className="text-lg font-semibold mb-4">Создать пригласительную ссылку</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название компании / группы</label>
            <input
              className="input w-full"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Например, Агрохолдинг «Терра»"
              required
              minLength={1}
              maxLength={255}
            />
          </div>

          <div>
            <span className="block text-sm font-medium text-gray-700 mb-2">Тип ссылки</span>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="perm" checked={permanent} onChange={() => setPermanent(true)} />
                <span>Постоянная</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="perm" checked={!permanent} onChange={() => setPermanent(false)} />
                <span>Временная</span>
              </label>
            </div>
          </div>

          {!permanent && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Срок действия (часов)</label>
              <input
                type="number"
                className="input w-full"
                min={1}
                max={8760}
                value={durationHours}
                onChange={(e) => setDurationHours(parseInt(e.target.value, 10) || 24)}
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Макс. переходов по ссылке</label>
            <input
              type="number"
              className="input w-full"
              min={1}
              placeholder="Без ограничения — оставьте пустым"
              value={maxVisits}
              onChange={(e) => setMaxVisits(e.target.value)}
            />
            <p className="text-xs text-gray-400 mt-1">Пусто = без лимита</p>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3">
              {(error as any)?.response?.data?.detail || "Ошибка создания ссылки"}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" className="flex-1 py-2 rounded-lg border border-gray-200" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="btn-primary flex-1 py-2" disabled={loading}>
              {loading ? "Создание…" : "Создать"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

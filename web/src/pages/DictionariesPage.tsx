import React, { useState } from "react";
import { api } from "../api/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Pencil, Check, X } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────
interface Activity { id: number; name: string; grp: string; pos: number }
interface Location  { id: number; name: string; grp: string; pos: number }
interface MachineKind { id: number; title: string; mode: string; pos: number }
interface MachineItem { id: number; kind_id: number; name: string; pos: number }
interface Crop { name: string; pos: number }

// ── API helpers ─────────────────────────────────────────────────────────────
const dictApi = {
  all:           () => api.get<{activities:Activity[];locations:Location[];machine_kinds:MachineKind[];machine_items:MachineItem[];crops:Crop[]}>("/dictionaries").then(r => r.data),

  addActivity:   (b: Omit<Activity,"id">) => api.post("/dictionaries/activities", b).then(r => r.data),
  delActivity:   (id: number) => api.delete(`/dictionaries/activities/${id}`),

  addLocation:   (b: Omit<Location,"id">) => api.post("/dictionaries/locations", b).then(r => r.data),
  delLocation:   (id: number) => api.delete(`/dictionaries/locations/${id}`),

  addKind:       (b: Omit<MachineKind,"id">) => api.post("/dictionaries/machine-kinds", b).then(r => r.data),
  delKind:       (id: number) => api.delete(`/dictionaries/machine-kinds/${id}`),

  addItem:       (b: Omit<MachineItem,"id">) => api.post("/dictionaries/machine-items", b).then(r => r.data),
  delItem:       (id: number) => api.delete(`/dictionaries/machine-items/${id}`),

  addCrop:       (b: { name: string; pos: number }) => api.post("/dictionaries/crops", b).then(r => r.data),
  delCrop:       (name: string) => api.delete(`/dictionaries/crops/${name}`),
};

// ── Reusable add-row form ───────────────────────────────────────────────────
function AddRow({ fields, onAdd }: {
  fields: { key: string; label: string; type?: string; options?: {value:string;label:string}[] }[];
  onAdd: (values: Record<string, string>) => void;
}) {
  const init = Object.fromEntries(fields.map(f => [f.key, f.options?.[0]?.value ?? ""]));
  const [vals, setVals] = useState<Record<string, string>>(init);
  const set = (k: string, v: string) => setVals(p => ({ ...p, [k]: v }));
  return (
    <div className="flex gap-2 mt-3 flex-wrap">
      {fields.map(f => (
        f.options ? (
          <select key={f.key} value={vals[f.key]} onChange={e => set(f.key, e.target.value)}
            className="border rounded-lg px-3 py-2 text-sm flex-1 min-w-[120px]">
            {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ) : (
          <input key={f.key} placeholder={f.label} value={vals[f.key]}
            onChange={e => set(f.key, e.target.value)} type={f.type || "text"}
            className="border rounded-lg px-3 py-2 text-sm flex-1 min-w-[120px]" />
        )
      ))}
      <button onClick={() => { onAdd(vals); setVals(init); }}
        className="bg-primary-700 text-white px-4 py-2 rounded-lg text-sm hover:bg-primary-800 flex items-center gap-1">
        <Plus size={14} /> Добавить
      </button>
    </div>
  );
}

// ── Generic list ────────────────────────────────────────────────────────────
function DictList({ items, getKey, getLabel, onDelete }: {
  items: any[]; getKey: (i: any) => string | number;
  getLabel: (i: any) => React.ReactNode; onDelete: (i: any) => void;
}) {
  if (!items.length) return <p className="text-gray-400 text-sm py-4 text-center">Список пуст</p>;
  return (
    <ul className="divide-y divide-gray-100">
      {items.map(item => (
        <li key={getKey(item)} className="flex items-center justify-between py-2 px-1 hover:bg-gray-50 rounded">
          <span className="text-sm text-gray-700">{getLabel(item)}</span>
          <button onClick={() => onDelete(item)} className="text-red-400 hover:text-red-600 p-1 rounded">
            <Trash2 size={14} />
          </button>
        </li>
      ))}
    </ul>
  );
}

// ── Section card ────────────────────────────────────────────────────────────
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <h3 className="font-semibold text-gray-800 mb-3 text-base">{title}</h3>
      {children}
    </div>
  );
}

// ── Tabs ────────────────────────────────────────────────────────────────────
const TABS = [
  { id: "otd",   label: "ОТД Отчёт" },
  { id: "brig",  label: "Отчёт бригадира" },
];

// ── Main Page ───────────────────────────────────────────────────────────────
export default function DictionariesPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"otd" | "brig">("otd");

  // ── Queries ──
  const { data: all } = useQuery({ queryKey: ["dict-all"], queryFn: dictApi.all });
  const activities = all?.activities ?? [];
  const locations  = all?.locations  ?? [];
  const kinds      = all?.machine_kinds ?? [];
  const items      = all?.machine_items ?? [];
  const crops      = all?.crops ?? [];

  const inv = () => qc.invalidateQueries({ queryKey: ["dict-all"] });

  const addActivity  = useMutation({ mutationFn: (v: Record<string,string>) => dictApi.addActivity({ name: v.name, grp: v.grp, pos: Number(v.pos) || 0 }), onSuccess: inv });
  const delActivity  = useMutation({ mutationFn: (id: number) => dictApi.delActivity(id), onSuccess: inv });

  const addLocation  = useMutation({ mutationFn: (v: Record<string,string>) => dictApi.addLocation({ name: v.name, grp: v.grp, pos: Number(v.pos) || 0 }), onSuccess: inv });
  const delLocation  = useMutation({ mutationFn: (id: number) => dictApi.delLocation(id), onSuccess: inv });

  const addKind      = useMutation({ mutationFn: (v: Record<string,string>) => dictApi.addKind({ title: v.title, mode: v.mode, pos: Number(v.pos) || 0 }), onSuccess: inv });
  const delKind      = useMutation({ mutationFn: (id: number) => dictApi.delKind(id), onSuccess: inv });

  const addItem      = useMutation({ mutationFn: (v: Record<string,string>) => dictApi.addItem({ kind_id: Number(v.kind_id), name: v.name, pos: Number(v.pos) || 0 }), onSuccess: inv });
  const delItem      = useMutation({ mutationFn: (id: number) => dictApi.delItem(id), onSuccess: inv });

  const addCrop      = useMutation({ mutationFn: (v: Record<string,string>) => dictApi.addCrop({ name: v.name, pos: Number(v.pos) || 0 }), onSuccess: inv });
  const delCrop      = useMutation({ mutationFn: (name: string) => dictApi.delCrop(name), onSuccess: inv });

  const techActs = activities.filter(a => a.grp === "техника");
  const handActs = activities.filter(a => a.grp === "ручная");
  const polya    = locations.filter(l => l.grp === "поля");
  const sklad    = locations.filter(l => l.grp === "склад");

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Настройка справочников</h1>
        <p className="text-gray-500 text-sm mt-1">Управление данными для мобильных форм</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id as any)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t.id ? "bg-white shadow text-primary-700" : "text-gray-500 hover:text-gray-700"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── ОТД Отчёт ── */}
      {tab === "otd" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

          {/* Виды деятельности — Техника */}
          <Section title="🚜 Деятельность — Техника">
            <DictList items={techActs} getKey={i => i.id} getLabel={i => i.name}
              onDelete={i => delActivity.mutate(i.id)} />
            <AddRow
              fields={[{ key: "name", label: "Название" }, { key: "grp", label: "Группа", options: [{ value:"техника", label:"техника" }] }, { key: "pos", label: "Порядок", type: "number" }]}
              onAdd={v => addActivity.mutate(v)}
            />
          </Section>

          {/* Виды деятельности — Ручная */}
          <Section title="🙌 Деятельность — Ручная">
            <DictList items={handActs} getKey={i => i.id} getLabel={i => i.name}
              onDelete={i => delActivity.mutate(i.id)} />
            <AddRow
              fields={[{ key: "name", label: "Название" }, { key: "grp", label: "Группа", options: [{ value:"ручная", label:"ручная" }] }, { key: "pos", label: "Порядок", type: "number" }]}
              onAdd={v => addActivity.mutate(v)}
            />
          </Section>

          {/* Поля */}
          <Section title="🌾 Поля">
            <DictList items={polya} getKey={i => i.id} getLabel={i => i.name}
              onDelete={i => delLocation.mutate(i.id)} />
            <AddRow
              fields={[{ key: "name", label: "Название поля" }, { key: "grp", label: "Группа", options: [{ value:"поля", label:"поля" }] }, { key: "pos", label: "Порядок", type: "number" }]}
              onAdd={v => addLocation.mutate(v)}
            />
          </Section>

          {/* Склад */}
          <Section title="🏚️ Склад / прочие места">
            <DictList items={sklad} getKey={i => i.id} getLabel={i => i.name}
              onDelete={i => delLocation.mutate(i.id)} />
            <AddRow
              fields={[{ key: "name", label: "Название" }, { key: "grp", label: "Группа", options: [{ value:"склад", label:"склад" }] }, { key: "pos", label: "Порядок", type: "number" }]}
              onAdd={v => addLocation.mutate(v)}
            />
          </Section>

          {/* Типы техники */}
          <Section title="⚙️ Типы техники">
            <DictList items={kinds} getKey={i => i.id}
              getLabel={i => <span>{i.title} <span className="text-xs text-gray-400 ml-1">({i.mode})</span></span>}
              onDelete={i => delKind.mutate(i.id)} />
            <AddRow
              fields={[
                { key: "title", label: "Название" },
                { key: "mode", label: "Режим", options: [{ value:"list", label:"список" }, { value:"free", label:"свободный" }] },
                { key: "pos", label: "Порядок", type: "number" },
              ]}
              onAdd={v => addKind.mutate(v)}
            />
          </Section>

          {/* Единицы техники */}
          <Section title="🚛 Единицы техники">
            <DictList items={items} getKey={i => i.id}
              getLabel={i => {
                const k = kinds.find(k => k.id === i.kind_id);
                return <span>{i.name} <span className="text-xs text-gray-400 ml-1">[{k?.title || i.kind_id}]</span></span>;
              }}
              onDelete={i => delItem.mutate(i.id)} />
            <AddRow
              fields={[
                { key: "kind_id", label: "Тип", options: kinds.map(k => ({ value: String(k.id), label: k.title })) },
                { key: "name", label: "Название" },
                { key: "pos", label: "Порядок", type: "number" },
              ]}
              onAdd={v => addItem.mutate(v)}
            />
          </Section>

          {/* Культуры */}
          <Section title="🌱 Культуры">
            <DictList items={crops} getKey={i => i.name} getLabel={i => i.name}
              onDelete={i => delCrop.mutate(i.name)} />
            <AddRow
              fields={[{ key: "name", label: "Культура" }, { key: "pos", label: "Порядок", type: "number" }]}
              onAdd={v => addCrop.mutate(v)}
            />
          </Section>
        </div>
      )}

      {/* ── Отчёт бригадира ── */}
      {tab === "brig" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

          {/* Поля для отчётов бригадира */}
          <Section title="🌾 Поля (для бригадира)">
            <DictList items={polya} getKey={i => i.id} getLabel={i => i.name}
              onDelete={i => delLocation.mutate(i.id)} />
            <AddRow
              fields={[{ key: "name", label: "Название поля" }, { key: "grp", label: "Группа", options: [{ value:"поля", label:"поля" }] }, { key: "pos", label: "Порядок", type: "number" }]}
              onAdd={v => addLocation.mutate(v)}
            />
          </Section>

          {/* Виды работ для бригадира */}
          <Section title="🙌 Виды работ (бригадир)">
            <DictList items={handActs} getKey={i => i.id} getLabel={i => i.name}
              onDelete={i => delActivity.mutate(i.id)} />
            <AddRow
              fields={[{ key: "name", label: "Вид работы" }, { key: "grp", label: "Группа", options: [{ value:"ручная", label:"ручная" }] }, { key: "pos", label: "Порядок", type: "number" }]}
              onAdd={v => addActivity.mutate(v)}
            />
          </Section>

          {/* Культуры */}
          <Section title="🌱 Культуры">
            <DictList items={crops} getKey={i => i.name} getLabel={i => i.name}
              onDelete={i => delCrop.mutate(i.name)} />
            <AddRow
              fields={[{ key: "name", label: "Культура" }, { key: "pos", label: "Порядок", type: "number" }]}
              onAdd={v => addCrop.mutate(v)}
            />
          </Section>

        </div>
      )}
    </div>
  );
}

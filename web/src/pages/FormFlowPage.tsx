import React, { useState, useCallback, useEffect, useRef } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Save, Trash2, ChevronDown, ChevronRight,
  Calendar, Hash, List, Type, CheckSquare, Flag, X, Edit2, Pencil,
} from "lucide-react";
import { api } from "../api/client";
import { toast } from "../components/Toast";

// ─── Error Boundary ───────────────────────────────────────────────────────
class FlowErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("FlowEditor error:", error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
          <div className="text-3xl mb-3">⚠️</div>
          <p className="font-semibold text-red-600 mb-1">Произошла ошибка в редакторе</p>
          <p className="text-sm text-gray-500 mb-4">{this.state.error.message}</p>
          <button
            className="btn-primary px-4 py-2 text-sm"
            onClick={() => this.setState({ error: null })}
          >
            Попробовать снова
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Types ────────────────────────────────────────────────────────────────
type StepType = "start" | "date" | "number" | "choice" | "text" | "confirm";

interface ConditionalNext { option: string; nextId: string }

interface FlowNode {
  id: string;
  type: StepType;
  label: string;
  options?: string[];
  source?: string; // dict source for choice nodes without static options
  defaultNextId?: string;
  conditionalNext?: ConditionalNext[];
  position: { x: number; y: number };
}

interface FormFlow { nodes: FlowNode[]; startId: string }

interface FormTemplate {
  id: number;
  name: string;
  title: string;
  schema: { fields: any[]; flow?: FormFlow };
  is_active: boolean;
  roles: string[];
  created_at: string;
}

const ROLES = ["user", "brigadier", "tim", "it", "accountant"];
const ROLE_LABELS: Record<string, string> = {
  user: "Сотрудник", brigadier: "Бригадир", tim: "ТИМ", it: "IT", accountant: "Бухгалтер",
};

const STEP_ICONS: Record<StepType, React.ReactNode> = {
  start:   <Flag size={14} className="text-green-600" />,
  date:    <Calendar size={14} className="text-blue-500" />,
  number:  <Hash size={14} className="text-orange-500" />,
  choice:  <List size={14} className="text-purple-500" />,
  text:    <Type size={14} className="text-gray-500" />,
  confirm: <CheckSquare size={14} className="text-green-600" />,
};

const STEP_LABELS: Record<StepType, string> = {
  start: "Начало", date: "Дата", number: "Число", choice: "Выбор", text: "Текст", confirm: "Подтверждение",
};

const STEP_COLORS: Record<StepType, string> = {
  start:   "border-green-400 bg-green-50",
  date:    "border-blue-300 bg-blue-50",
  number:  "border-orange-300 bg-orange-50",
  choice:  "border-purple-300 bg-purple-50",
  text:    "border-gray-300 bg-gray-50",
  confirm: "border-green-500 bg-green-100",
};

// ─── Default OTD flow ────────────────────────────────────────────────────
const OTD_FLOW: FormFlow = {
  startId: "start",
  nodes: [
    { id: "start",        type: "start",   label: "Начало",            position: { x: 250, y: 20 },  defaultNextId: "date" },
    { id: "date",         type: "date",    label: "Дата работы",        position: { x: 250, y: 110 }, defaultNextId: "hours" },
    { id: "hours",        type: "number",  label: "Количество часов",   position: { x: 250, y: 200 }, defaultNextId: "work_type" },
    { id: "work_type",    type: "choice",  label: "Тип работ",          position: { x: 250, y: 290 },
      options: ["Техника", "Ручная"],
      conditionalNext: [
        { option: "Техника", nextId: "machine_type" },
        { option: "Ручная",  nextId: "activity_hand" },
      ]},
    { id: "machine_type", type: "choice",  label: "Тип техники",        position: { x: 50,  y: 420 }, source: "machine_kinds",    defaultNextId: "activity_tech" },
    { id: "activity_tech",type: "choice",  label: "Вид деятельности",   position: { x: 50,  y: 520 }, source: "activities_tech",  defaultNextId: "location_tech" },
    { id: "location_tech",type: "choice",  label: "Поле / Склад",       position: { x: 50,  y: 620 }, source: "locations",        defaultNextId: "trips" },
    { id: "trips",        type: "number",  label: "Количество рейсов",  position: { x: 50,  y: 720 }, defaultNextId: "crop_tech" },
    { id: "crop_tech",    type: "choice",  label: "Культура",           position: { x: 50,  y: 820 }, source: "crops",            defaultNextId: "confirm" },
    { id: "activity_hand",type: "choice",  label: "Вид ручной работы",  position: { x: 450, y: 420 }, source: "activities_hand",  defaultNextId: "location_hand" },
    { id: "location_hand",type: "choice",  label: "Поле / Склад",       position: { x: 450, y: 520 }, source: "locations",        defaultNextId: "crop_hand" },
    { id: "crop_hand",    type: "choice",  label: "Культура",           position: { x: 450, y: 620 }, source: "crops",            defaultNextId: "confirm" },
    { id: "confirm",      type: "confirm", label: "Подтверждение",      position: { x: 250, y: 940 } },
  ],
};

const BRIG_FLOW: FormFlow = {
  startId: "start",
  nodes: [
    { id: "start",    type: "start",   label: "Начало",          position: { x: 200, y: 20 },  defaultNextId: "date" },
    { id: "date",     type: "date",    label: "Дата работы",      position: { x: 200, y: 110 }, defaultNextId: "work_type" },
    { id: "work_type",type: "choice",  label: "Вид работ",        position: { x: 200, y: 200 }, source: "activities_tech", defaultNextId: "field" },
    { id: "field",    type: "choice",  label: "Поле",             position: { x: 200, y: 300 }, source: "locations_field", defaultNextId: "shift" },
    { id: "shift",    type: "choice",  label: "Смена",            position: { x: 200, y: 400 }, options: ["1", "2", "3"],  defaultNextId: "rows" },
    { id: "rows",     type: "number",  label: "Рядков",           position: { x: 200, y: 500 }, defaultNextId: "bags" },
    { id: "bags",     type: "number",  label: "Мешков",           position: { x: 200, y: 600 }, defaultNextId: "workers" },
    { id: "workers",  type: "number",  label: "Кол-во рабочих",   position: { x: 200, y: 700 }, defaultNextId: "confirm" },
    { id: "confirm",  type: "confirm", label: "Подтверждение",    position: { x: 200, y: 800 } },
  ],
};

// ─── Convert FlowNode[] → ReactFlow nodes + edges ───────────────────────
function flowToRF(flow: FormFlow): { nodes: Node[]; edges: Edge[] } {
  const rfNodes: Node[] = flow.nodes.map((n) => ({
    id: n.id,
    type: "stepNode",
    position: n.position,
    data: { ...n },
    draggable: true,
  }));

  const rfEdges: Edge[] = [];
  for (const n of flow.nodes) {
    if (n.conditionalNext?.length) {
      for (const c of n.conditionalNext) {
        rfEdges.push({
          id: `${n.id}-${c.nextId}-${c.option}`,
          source: n.id,
          target: c.nextId,
          label: c.option,
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: "#6366f1" },
          labelStyle: { fontSize: 11, fontWeight: 600, fill: "#6366f1" },
          labelBgStyle: { fill: "#eef2ff", rx: 4 },
        });
      }
    } else if (n.defaultNextId) {
      rfEdges.push({
        id: `${n.id}-${n.defaultNextId}`,
        source: n.id,
        target: n.defaultNextId,
        animated: false,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: "#1a5c2e" },
      });
    }
  }
  return { nodes: rfNodes, edges: rfEdges };
}

// ─── Convert back RF state → FlowNode[] ────────────────────────────────
function rfToFlow(rfNodes: Node[], rfEdges: Edge[], startId: string): FormFlow {
  const nodes: FlowNode[] = rfNodes.map((n) => {
    const data = n.data as unknown as FlowNode;
    const outEdges = rfEdges.filter((e) => e.source === n.id);
    const conditionalEdges = outEdges.filter((e) => e.label);
    const defaultEdge = outEdges.find((e) => !e.label);

    return {
      id: n.id,
      type: data.type,
      label: data.label,
      source: data.source,
      options: !data.source ? (data.options ?? undefined) : undefined,
      position: n.position,
      defaultNextId: defaultEdge?.target ?? undefined,
      conditionalNext: conditionalEdges.length
        ? conditionalEdges.map((e) => ({ option: String(e.label), nextId: e.target }))
        : undefined,
    };
  });
  return { nodes, startId };
}

// ─── Custom Node Component ────────────────────────────────────────────────
function StepNode({ data, selected }: NodeProps) {
  const d = data as unknown as FlowNode & { isSwapSource?: boolean };
  const isStart = d.type === "start";
  const isConfirm = d.type === "confirm";
  const { dictMap } = React.useContext(DictContext);

  // Resolve options: static options OR from dict context
  const resolvedOptions: string[] =
    d.type === "choice"
      ? (d.source ? (dictMap[d.source] ?? []) : (d.options ?? []))
      : [];

  return (
    <div
      className={`border-2 rounded-xl px-4 py-3 min-w-[160px] max-w-[200px] shadow-sm transition-shadow ${STEP_COLORS[d.type]} ${selected ? "ring-2 ring-indigo-400 shadow-lg" : ""} ${d.isSwapSource ? "ring-4 ring-orange-400 ring-offset-1 shadow-xl" : ""}`}
      style={{ fontSize: 13 }}
    >
      {!isStart && (
        <Handle type="target" position={Position.Top} style={{ background: "#1a5c2e", width: 10, height: 10 }} />
      )}

      <div className="flex items-center gap-2 mb-1">
        {STEP_ICONS[d.type]}
        <span className="text-xs font-bold text-gray-400 uppercase tracking-wide">{STEP_LABELS[d.type]}</span>
      </div>
      <div className="font-semibold text-gray-800 leading-tight">{d.label}</div>

      {d.type === "choice" && d.source && (
        <div className="mt-1 mb-1 text-xs text-purple-400 italic">из словаря</div>
      )}

      {d.type === "choice" && resolvedOptions.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {resolvedOptions.slice(0, 4).map((opt) => (
            <div key={opt} className="text-xs bg-white/70 border border-purple-200 rounded px-2 py-0.5 text-purple-700 truncate">
              {opt}
            </div>
          ))}
          {resolvedOptions.length > 4 && (
            <div className="text-xs text-purple-400 px-2">+{resolvedOptions.length - 4} ещё…</div>
          )}
        </div>
      )}

      {d.type === "choice" && resolvedOptions.length === 0 && (
        <div className="mt-1 text-xs text-amber-500 italic">⚠ варианты не заданы</div>
      )}

      {!isConfirm && (
        <Handle type="source" position={Position.Bottom} style={{ background: "#1a5c2e", width: 10, height: 10 }} />
      )}
    </div>
  );
}

const NODE_TYPES = { stepNode: StepNode };

// Context to pass dicts + custom dict metadata into ReactFlow custom nodes
interface DictContextValue {
  dictMap: Record<string, string[]>;
  customDictMeta: { id: number; name: string }[];
  // kind title -> mode ("list" | "choices" | "message" | "")
  kindModes: Record<string, string>;
}
const DictContext = React.createContext<DictContextValue>({ dictMap: {}, customDictMeta: [], kindModes: {} });

// ─── Node Edit Panel ──────────────────────────────────────────────────────
const STATIC_SOURCES = [
  { value: "",                label: "— статические варианты —" },
  { value: "machine_kinds",   label: "📋 Типы техники" },
  { value: "machine_items",   label: "🚛 Единицы техники (все)" },
  { value: "activities_tech", label: "🚜 Деятельность — Техника" },
  { value: "activities_hand", label: "🙌 Деятельность — Ручная" },
  { value: "locations",       label: "📍 Все локации" },
  { value: "locations_field", label: "🌾 Поля" },
  { value: "locations_store", label: "🏚 Склад / прочее" },
  { value: "crops",           label: "🌱 Культуры" },
];

function NodeEditPanel({
  node,
  allNodes,
  onUpdate,
  onDelete,
  onClose,
  onSetChain,
}: {
  node: Node;
  allNodes: Node[];
  onUpdate: (id: string, data: Partial<FlowNode>) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  onSetChain: (nodeId: string, item: string, seqNodeIds: string[]) => void;
}) {
  const d = node.data as unknown as FlowNode;
  const { dictMap, customDictMeta, kindModes } = React.useContext(DictContext);

  // Build dynamic sources — add per-kind machine_items + custom dicts
  const SOURCES = React.useMemo(() => {
    const kindEntries = Object.keys(dictMap)
      .filter((k) => k.startsWith("machine_items:"))
      .sort()
      .map((k) => {
        const kindName = k.replace("machine_items:", "");
        return { value: k, label: `🚛 ${kindName} (список)` };
      });
    const customEntries = customDictMeta.map((cd) => ({
      value: `custom:${cd.id}`,
      label: `📂 ${cd.name}`,
    }));
    const machineIdx = STATIC_SOURCES.findIndex((s) => s.value === "machine_items");
    const result = [...STATIC_SOURCES];
    result.splice(machineIdx + 1, 0, ...kindEntries);
    return [...result, ...customEntries];
  }, [dictMap, customDictMeta]);

  const [label, setLabel] = useState(d.label);
  const [type, setType] = useState<StepType>(d.type);
  const [source, setSource] = useState(d.source || "");
  const [defaultNext, setDefaultNext] = useState(d.defaultNextId || "");

  // Static options (no source)
  const [options, setOptions] = useState<string[]>(d.options || []);
  const [optInput, setOptInput] = useState("");
  const [condNext, setCondNext] = useState<ConditionalNext[]>(d.conditionalNext || []);

  // Source-based branching: "single path (+ exceptions)" vs "per-item full branches"
  // Full branches mode = conditionalNext set AND no defaultNextId (every item has own route)
  // Single path mode = defaultNextId set (some items may have custom toggles via branchMap)
  const hasSavedBranches = (d.conditionalNext?.length ?? 0) > 0 && !!d.source && !d.defaultNextId;
  const [useBranching, setUseBranching] = useState(hasSavedBranches);
  // per-item next map: { "Трактор": "nodeId", "КамАЗ": "nodeId2" }
  const [branchMap, setBranchMap] = useState<Record<string, string>>(() => {
    const m: Record<string, string> = {};
    (d.conditionalNext || []).forEach((c) => { m[c.option] = c.nextId; });
    return m;
  });

  const otherNodes = allNodes.filter((n) => n.id !== node.id);
  const sourceItems = source ? (dictMap[source] ?? []) : [];

  // Sequence builder state: which item is being chained, and the steps
  const [seqFor, setSeqFor] = useState<string | null>(null);
  const [seqSteps, setSeqSteps] = useState<string[]>([]);

  const openSeqBuilder = (item: string) => {
    if (seqFor === item) { setSeqFor(null); return; }
    setSeqFor(item);
    // Pre-fill with current branch target if set
    setSeqSteps(branchMap[item] ? [branchMap[item]] : []);
  };

  const applyChain = (item: string, steps: string[]) => {
    if (steps.length === 0 || steps.some((s) => !s)) return;
    // 1. Apply chain to other nodes + edges immediately
    onSetChain(node.id, item, steps);
    // 2. Update local branchMap so it's reflected in save()
    const newBranchMap = { ...branchMap, [item]: steps[0] };
    setBranchMap(newBranchMap);
    // 3. Auto-save this node with updated conditionalNext
    const branches = sourceItems
      .filter((i) => newBranchMap[i])
      .map((i) => ({ option: i, nextId: newBranchMap[i] }));
    onUpdate(node.id, {
      label, type,
      source: source || undefined,
      options: undefined,
      conditionalNext: branches.length ? branches : undefined,
      defaultNextId: defaultNext || undefined,
    });
    setSeqFor(null);
  };

  // When source changes, reset branching state
  const handleSourceChange = (v: string) => {
    setSource(v);
    setUseBranching(false);
    setBranchMap({});
    setDefaultNext("");
  };

  const setBranchTarget = (item: string, nextId: string) =>
    setBranchMap((m) => ({ ...m, [item]: nextId }));

  // Static option helpers
  const addOpt = () => {
    if (!optInput.trim()) return;
    const o = optInput.trim();
    setOptions([...options, o]);
    setCondNext([...condNext, { option: o, nextId: "" }]);
    setOptInput("");
  };
  const removeOpt = (i: number) => {
    const o = options[i];
    setOptions(options.filter((_, j) => j !== i));
    setCondNext(condNext.filter((c) => c.option !== o));
  };
  const setCondTarget = (option: string, nextId: string) =>
    setCondNext(condNext.map((c) => c.option === option ? { ...c, nextId } : c));

  const save = () => {
    let conditionalNext: ConditionalNext[] | undefined;
    let savedDefaultNext: string | undefined;

    if (type === "choice") {
      if (!source) {
        // Static options mode
        conditionalNext = condNext.length ? condNext : undefined;
        savedDefaultNext = undefined;
      } else if (useBranching && sourceItems.length > 0) {
        // Per-item branching from dict
        const branches = sourceItems
          .filter((item) => branchMap[item])
          .map((item) => ({ option: item, nextId: branchMap[item] }));
        conditionalNext = branches.length ? branches : undefined;
        savedDefaultNext = defaultNext || undefined;
      } else {
        // Single path for all dict items + optional per-item exceptions (флашки)
        savedDefaultNext = defaultNext || undefined;
        const exceptions = Object.entries(branchMap)
          .filter(([, nextId]) => !!nextId)
          .map(([option, nextId]) => ({ option, nextId }));
        conditionalNext = exceptions.length ? exceptions : undefined;
      }
    } else {
      savedDefaultNext = defaultNext || undefined;
      conditionalNext = undefined;
    }

    onUpdate(node.id, {
      label,
      type,
      source: type === "choice" ? (source || undefined) : undefined,
      options: type === "choice" && !source ? options : undefined,
      conditionalNext,
      defaultNextId: savedDefaultNext,
    });
    onClose();
  };

  return (
    <div className="w-80 bg-white border-l border-gray-200 flex flex-col h-full shadow-lg z-10">
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
        <span className="font-semibold text-sm text-gray-700">Редактор шага</span>
        <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded"><X size={14} /></button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Label */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Название шага</label>
          <input className="input text-sm" value={label} onChange={(e) => setLabel(e.target.value)} />
        </div>

        {/* Type */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Тип шага</label>
          <select className="input text-sm" value={type}
            onChange={(e) => setType(e.target.value as StepType)}
            disabled={d.type === "start" || d.type === "confirm"}>
            {(["date", "number", "choice", "text"] as StepType[]).map((t) => (
              <option key={t} value={t}>{STEP_LABELS[t]}</option>
            ))}
          </select>
        </div>

        {/* ── CHOICE config ── */}
        {type === "choice" && (
          <div className="space-y-3">
            {/* Source selector */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">Источник вариантов</label>
              <select className="input text-xs" value={source} onChange={(e) => handleSourceChange(e.target.value)}>
                {SOURCES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>

            {/* ── SOURCE mode ── */}
            {source && (
              <div className="border border-purple-200 rounded-xl overflow-hidden">
                {/* Branching toggle */}
                <div className="bg-purple-50 px-3 py-2 flex items-center justify-between">
                  <span className="text-xs text-purple-700 font-medium">
                    {SOURCES.find((s) => s.value === source)?.label}
                  </span>
                  <button
                    className={`text-xs px-2 py-0.5 rounded-full font-medium border transition-colors ${
                      useBranching
                        ? "bg-indigo-600 text-white border-indigo-600"
                        : "bg-white text-gray-500 border-gray-300 hover:border-indigo-400"
                    }`}
                    onClick={() => setUseBranching((v) => !v)}
                  >
                    {useBranching ? "✦ Разные ветки" : "→ Один путь"}
                  </button>
                </div>

                {/* Per-item branching */}
                {useBranching && (
                  <div className="p-3 space-y-2">
                    <p className="text-xs text-gray-400 mb-2">
                      Для каждого значения словаря — свой следующий шаг:
                    </p>
                    {sourceItems.length === 0 ? (
                      <p className="text-xs text-amber-500">⚠ Словарь пустой — сначала добавьте значения слева</p>
                    ) : (
                      sourceItems.map((item) => {
                        const kMode = source === "machine_kinds" ? (kindModes[item] ?? "list") : null;
                        const autoLabel =
                          kMode === "list"    ? `📋 авто: список ${item}` :
                          kMode === "choices" ? `☑ авто: выбор` :
                          kMode === "message" ? `💬 авто: сообщение` : null;
                        const isSeqOpen = seqFor === item;
                        return (
                          <div key={item} className={`rounded-lg p-2 ${isSeqOpen ? "bg-indigo-50 border border-indigo-300" : "bg-purple-50"}`}>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-semibold text-purple-700 truncate flex-1">{item}</span>
                              {autoLabel && (
                                <span className="text-[10px] bg-indigo-100 text-indigo-600 px-1.5 py-0.5 rounded-full flex-shrink-0">
                                  {autoLabel}
                                </span>
                              )}
                              {/* Chain sequence builder trigger */}
                              <button
                                title="Настроить цепочку шагов для этого пункта"
                                onClick={() => openSeqBuilder(item)}
                                className={`flex-shrink-0 text-xs px-1.5 py-0.5 rounded border transition-colors ${
                                  isSeqOpen
                                    ? "bg-indigo-600 text-white border-indigo-600"
                                    : "bg-white text-indigo-500 border-indigo-300 hover:bg-indigo-50"
                                }`}
                              >
                                🔗
                              </button>
                            </div>
                            {autoLabel && !isSeqOpen && (
                              <p className="text-[10px] text-gray-400 mb-1">
                                Шаг <strong>после</strong> авто-экрана:
                              </p>
                            )}
                            {!isSeqOpen && (
                              <select
                                className="input text-xs py-1"
                                value={branchMap[item] || ""}
                                onChange={(e) => setBranchTarget(item, e.target.value)}
                              >
                                <option value="">→ (не задан)</option>
                                {otherNodes.map((n) => (
                                  <option key={n.id} value={n.id}>{(n.data as unknown as FlowNode).label}</option>
                                ))}
                              </select>
                            )}

                            {/* ── Inline sequence builder ── */}
                            {isSeqOpen && (
                              <div className="mt-2 space-y-2">
                                <p className="text-[11px] text-indigo-600 font-semibold">
                                  Цепочка шагов для «{item}»:
                                </p>
                                {seqSteps.length === 0 && (
                                  <p className="text-[10px] text-gray-400">Добавьте шаги в нужном порядке ↓</p>
                                )}
                                {seqSteps.map((stepId, i) => (
                                  <div key={i} className="flex items-center gap-1">
                                    <span className="text-[10px] text-indigo-400 font-bold w-4 text-center">{i + 1}</span>
                                    <select
                                      className="input text-xs py-0.5 flex-1"
                                      value={stepId}
                                      onChange={(e) => {
                                        const updated = [...seqSteps];
                                        updated[i] = e.target.value;
                                        setSeqSteps(updated);
                                      }}
                                    >
                                      <option value="">— выберите шаг —</option>
                                      {otherNodes.map((n) => (
                                        <option key={n.id} value={n.id}>{(n.data as unknown as FlowNode).label}</option>
                                      ))}
                                    </select>
                                    <button
                                      onClick={() => setSeqSteps(seqSteps.filter((_, j) => j !== i))}
                                      className="text-red-400 hover:text-red-600 p-0.5"
                                    >
                                      <X size={10} />
                                    </button>
                                  </div>
                                ))}
                                <button
                                  className="text-xs text-indigo-500 hover:text-indigo-700 font-medium"
                                  onClick={() => setSeqSteps([...seqSteps, ""])}
                                >
                                  + Добавить шаг
                                </button>
                                <div className="flex gap-2 pt-1">
                                  <button
                                    className="flex-1 text-xs bg-indigo-600 text-white rounded-lg py-1.5 font-semibold hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
                                    disabled={seqSteps.length === 0 || seqSteps.some((s) => !s)}
                                    onClick={() => applyChain(item, seqSteps)}
                                  >
                                    ✓ Готово
                                  </button>
                                  <button
                                    className="px-3 text-xs border border-gray-300 rounded-lg py-1.5 text-gray-500 hover:bg-gray-50"
                                    onClick={() => setSeqFor(null)}
                                  >
                                    Отмена
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                    <div className="border-t pt-2">
                      <label className="block text-xs text-gray-400 mb-1">Путь по умолчанию (если не задан выше)</label>
                      <select className="input text-xs" value={defaultNext} onChange={(e) => setDefaultNext(e.target.value)}>
                        <option value="">— нет —</option>
                        {otherNodes.map((n) => (
                          <option key={n.id} value={n.id}>{(n.data as unknown as FlowNode).label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                {/* Single path + per-item exception toggles (флашки) */}
                {!useBranching && (
                  <div className="p-3 space-y-3">
                    {/* Default next step */}
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Следующий шаг (для всех вариантов)</label>
                      <select className="input text-sm" value={defaultNext} onChange={(e) => setDefaultNext(e.target.value)}>
                        <option value="">— не задан —</option>
                        {otherNodes.map((n) => (
                          <option key={n.id} value={n.id}>{(n.data as unknown as FlowNode).label}</option>
                        ))}
                      </select>
                    </div>

                    {/* Per-item exception toggles */}
                    {sourceItems.length > 0 && (
                      <div>
                        <p className="text-[11px] text-gray-400 mb-1.5 font-medium uppercase tracking-wide">
                          Ответвления для отдельных пунктов
                        </p>
                        <div className="space-y-1.5">
                          {sourceItems.map((item) => {
                            const hasEx = !!branchMap[item];
                            return (
                              <div key={item} className={`rounded-lg transition-colors ${hasEx ? "bg-indigo-50 border border-indigo-200" : "bg-gray-50"} p-2`}>
                                <div className="flex items-center gap-2">
                                  {/* Toggle switch (флашок) */}
                                  <button
                                    type="button"
                                    title={hasEx ? "Отключить ответвление" : "Включить ответвление"}
                                    onClick={() => {
                                      if (hasEx) {
                                        setBranchTarget(item, "");
                                      } else {
                                        setBranchTarget(item, defaultNext || "");
                                      }
                                    }}
                                    className={`relative inline-flex h-4 w-7 flex-shrink-0 items-center rounded-full transition-colors ${
                                      hasEx ? "bg-indigo-500" : "bg-gray-300"
                                    }`}
                                  >
                                    <span className={`inline-block h-3 w-3 transform rounded-full bg-white shadow transition-transform ${
                                      hasEx ? "translate-x-3.5" : "translate-x-0.5"
                                    }`} />
                                  </button>
                                  <span className={`text-xs font-medium flex-1 truncate ${hasEx ? "text-indigo-700" : "text-gray-500"}`}>
                                    {item}
                                  </span>
                                </div>
                                {/* Custom next step for this exception */}
                                {hasEx && (
                                  <div className="mt-1.5 flex items-center gap-1.5">
                                    <span className="text-[10px] text-indigo-400">→</span>
                                    <select
                                      className="input text-xs py-0.5 flex-1"
                                      value={branchMap[item]}
                                      onChange={(e) => setBranchTarget(item, e.target.value)}
                                    >
                                      <option value="">— не задан —</option>
                                      {otherNodes.map((n) => (
                                        <option key={n.id} value={n.id}>{(n.data as unknown as FlowNode).label}</option>
                                      ))}
                                    </select>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── STATIC options mode ── */}
            {!source && (
              <div>
                <label className="block text-xs text-gray-500 mb-2">Варианты и переходы</label>
                <div className="space-y-2">
                  {options.map((opt, i) => {
                    const cond = condNext.find((c) => c.option === opt);
                    return (
                      <div key={i} className="border rounded-lg p-2 bg-purple-50">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold text-purple-700 flex-1">{opt}</span>
                          <button onClick={() => removeOpt(i)} className="text-red-400 hover:text-red-600">
                            <X size={12} />
                          </button>
                        </div>
                        <select
                          className="input text-xs py-1"
                          value={cond?.nextId || ""}
                          onChange={(e) => setCondTarget(opt, e.target.value)}
                        >
                          <option value="">→ (не задан)</option>
                          {otherNodes.map((n) => (
                            <option key={n.id} value={n.id}>{(n.data as unknown as FlowNode).label}</option>
                          ))}
                        </select>
                      </div>
                    );
                  })}
                </div>
                <div className="flex gap-1 mt-2">
                  <input
                    className="input text-xs flex-1"
                    placeholder="Новый вариант..."
                    value={optInput}
                    onChange={(e) => setOptInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addOpt()}
                  />
                  <button className="btn-secondary text-xs px-2" onClick={addOpt}>+</button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Non-choice next step */}
        {type !== "choice" && d.type !== "confirm" && (
          <div>
            <label className="block text-xs text-gray-500 mb-1">Следующий шаг</label>
            <select className="input text-sm" value={defaultNext} onChange={(e) => setDefaultNext(e.target.value)}>
              <option value="">— нет —</option>
              {otherNodes.map((n) => (
                <option key={n.id} value={n.id}>{(n.data as unknown as FlowNode).label}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="p-4 border-t space-y-2">
        <button className="btn-primary w-full text-sm" onClick={save}>Применить</button>
        {d.type !== "start" && d.type !== "confirm" && (
          <button
            className="w-full py-2 text-sm text-red-500 hover:bg-red-50 rounded-lg border border-red-200"
            onClick={() => { onDelete(node.id); onClose(); }}
          >
            Удалить шаг
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Flow Editor ──────────────────────────────────────────────────────────
function FlowEditor({ form, onSaved }: { form: FormTemplate; onSaved: () => void }) {
  const qc = useQueryClient();
  const { getViewport } = useReactFlow();
  const containerRef = useRef<HTMLDivElement>(null);
  const [swapSourceId, setSwapSourceId] = useState<string | null>(null);

  // Load dicts to show real values in canvas nodes
  const { data: dicts } = useQuery({ queryKey: ["dict-all"], queryFn: dictApi.all });
  const dictMap: Record<string, string[]> = React.useMemo(() => {
    if (!dicts) return {};
    const base: Record<string, string[]> = {
      machine_kinds:   dicts.machine_kinds.map((k) => k.title),
      machine_items:   dicts.machine_items.map((i) => i.name),
      activities_tech: dicts.activities.filter((a) => a.grp === "техника").map((a) => a.name),
      activities_hand: dicts.activities.filter((a) => a.grp === "ручная").map((a) => a.name),
      locations:       dicts.locations.map((l) => l.name),
      locations_field: dicts.locations.filter((l) => l.grp === "поля").map((l) => l.name),
      locations_store: dicts.locations.filter((l) => l.grp === "склад").map((l) => l.name),
      crops:           dicts.crops.map((c) => c.name),
    };
    // Per-kind machine items
    dicts.machine_kinds.forEach((k) => {
      base[`machine_items:${k.title}`] = dicts.machine_items
        .filter((i) => i.kind_id === k.id)
        .map((i) => i.name);
    });
    // Custom dicts: "custom:ID"
    (dicts.custom_dicts ?? []).forEach((d) => {
      base[`custom:${d.id}`] = d.items.map((i) => i.value);
    });
    return base;
  }, [dicts]);

  const customDictMeta: { id: number; name: string }[] = React.useMemo(
    () => (dicts?.custom_dicts ?? []).map((d) => ({ id: d.id, name: d.name })),
    [dicts]
  );

  // kind title → mode, for showing auto-inject hints in NodeEditPanel
  const kindModes: Record<string, string> = React.useMemo(() => {
    const m: Record<string, string> = {};
    (dicts?.machine_kinds ?? []).forEach((k) => { m[k.title] = k.mode ?? "list"; });
    return m;
  }, [dicts]);

  const draftKey = `flow-draft-${form.id}`;
  const [hasDraft, setHasDraft] = useState(false);

  const getInitialFlow = (useDraft = true): FormFlow => {
    // Prefer sessionStorage draft (survives crashes/error boundary resets)
    if (useDraft) {
      try {
        const raw = sessionStorage.getItem(draftKey);
        if (raw) {
          const draft: FormFlow = JSON.parse(raw);
          if (draft?.nodes?.length) return draft;
        }
      } catch { /* ignore */ }
    }
    if (form.schema?.flow?.nodes?.length) return form.schema.flow;
    if (form.name === "otd") return OTD_FLOW;
    if (form.name === "brig") return BRIG_FLOW;
    return {
      startId: "start",
      nodes: [
        { id: "start",   type: "start",   label: "Начало",         position: { x: 200, y: 50 }, defaultNextId: "confirm" },
        { id: "confirm", type: "confirm", label: "Подтверждение",  position: { x: 200, y: 200 } },
      ],
    };
  };

  const initFlow = getInitialFlow();
  const { nodes: initRfNodes, edges: initRfEdges } = flowToRF(initFlow);
  // Detect if we loaded from a draft (not from saved schema)
  const initFromDraft = !!sessionStorage.getItem(draftKey);

  const [nodes, setNodes, onNodesChange] = useNodesState(initRfNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initRfEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [startId, setStartId] = useState(initFlow.startId);

  useEffect(() => { setHasDraft(initFromDraft); }, []);

  // Auto-save draft to sessionStorage on every change (crash recovery)
  useEffect(() => {
    const draft = rfToFlow(nodes, edges, startId);
    try { sessionStorage.setItem(draftKey, JSON.stringify(draft)); } catch { /* ignore */ }
  }, [nodes, edges, startId]);

  // Re-init when form changes (switching between forms)
  useEffect(() => {
    const f = getInitialFlow();
    const { nodes: rn, edges: re } = flowToRF(f);
    setNodes(rn);
    setEdges(re);
    setStartId(f.startId);
    setSelectedNode(null);
    setHasDraft(!!sessionStorage.getItem(draftKey));
  }, [form.id]);

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) => addEdge({ ...params, animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: "#1a5c2e" } }, eds)),
    [setEdges]
  );

  // Always-fresh refs so mutationFn captures current state (avoids stale closure bug)
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const startIdRef = useRef(startId);
  const formSchemaRef = useRef(form.schema);
  useEffect(() => { nodesRef.current = nodes; }, [nodes]);
  useEffect(() => { edgesRef.current = edges; }, [edges]);
  useEffect(() => { startIdRef.current = startId; }, [startId]);
  useEffect(() => { formSchemaRef.current = form.schema; }, [form.schema]);

  const saveMutation = useMutation({
    mutationFn: () => {
      // Use refs to always get the latest state, never stale closure values
      const flow = rfToFlow(nodesRef.current, edgesRef.current, startIdRef.current);
      return api.patch(`/forms/${form.id}`, { schema: { ...formSchemaRef.current, flow } })
        .then((res) => ({ flow, res }));
    },
    onSuccess: ({ flow }) => {
      // Synchronously update cache so remount sees fresh data immediately
      qc.setQueryData<FormTemplate[]>(["forms-admin"], (old) =>
        old?.map((f) =>
          f.id === form.id ? { ...f, schema: { ...f.schema, flow } } : f
        ) ?? []
      );
      // Also invalidate to eventually get a fresh server copy
      qc.invalidateQueries({ queryKey: ["forms-admin"] });
      // Clear draft — it's now officially saved
      try { sessionStorage.removeItem(draftKey); } catch { /* ignore */ }
      setHasDraft(false);
      toast("success", "Схема сохранена!");
      onSaved();
    },
    onError: () => toast("error", "Ошибка при сохранении"),
  });

  const addStep = (type: StepType) => {
    const id = `step_${Date.now()}`;
    // Calculate center of visible canvas in flow coordinates
    const { x: vx, y: vy, zoom } = getViewport();
    const w = containerRef.current?.clientWidth ?? 600;
    const h = containerRef.current?.clientHeight ?? 400;
    const position = {
      x: (-vx + w / 2) / zoom + (Math.random() - 0.5) * 80,
      y: (-vy + h / 2) / zoom + (Math.random() - 0.5) * 80,
    };
    const newNode: Node = {
      id,
      type: "stepNode",
      position,
      data: {
        id,
        type,
        label: STEP_LABELS[type],
        options: type === "choice" ? [] : undefined,
      } as unknown as Record<string, unknown>,
    };
    setNodes((ns) => [...ns, newNode]);
    setSelectedNode(newNode);
  };

  const updateNodeData = (id: string, updates: Partial<FlowNode>) => {
    setNodes((ns) =>
      ns.map((n) => n.id === id ? { ...n, data: { ...n.data, ...updates } } : n)
    );
    // rebuild edges for conditional changes
    if (updates.conditionalNext !== undefined || updates.defaultNextId !== undefined) {
      setEdges((eds) => {
        const kept = eds.filter((e) => e.source !== id);
        const newEdges: Edge[] = [];
        if (updates.conditionalNext?.length) {
          for (const c of updates.conditionalNext) {
            if (c.nextId) newEdges.push({
              id: `${id}-${c.nextId}-${c.option}`,
              source: id, target: c.nextId,
              label: c.option, animated: true,
              markerEnd: { type: MarkerType.ArrowClosed },
              style: { stroke: "#6366f1" },
              labelStyle: { fontSize: 11, fontWeight: 600, fill: "#6366f1" },
              labelBgStyle: { fill: "#eef2ff", rx: 4 },
            });
          }
        } else if (updates.defaultNextId) {
          newEdges.push({
            id: `${id}-${updates.defaultNextId}`,
            source: id, target: updates.defaultNextId,
            animated: false,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: "#1a5c2e" },
          });
        }
        return [...kept, ...newEdges];
      });
    }
  };

  const deleteNode = (id: string) => {
    setNodes((ns) => ns.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  };

  // Build a chain: nodeId -[item label]-> seq[0] -> seq[1] -> ... -> seq[n-1]
  // Also sets defaultNextId on each intermediate node in the chain.
  const handleSetChain = useCallback((nodeId: string, item: string, seqNodeIds: string[]) => {
    if (seqNodeIds.length === 0) return;

    // Update defaultNextId on each intermediate node (all except last)
    setNodes((ns) => ns.map((n) => {
      const idx = seqNodeIds.indexOf(n.id);
      if (idx >= 0 && idx < seqNodeIds.length - 1) {
        return { ...n, data: { ...n.data, defaultNextId: seqNodeIds[idx + 1] } };
      }
      return n;
    }));

    setEdges((eds) => {
      // Remove: old labeled edge from nodeId for this item
      //         AND old default (unlabeled) edges from intermediate nodes
      const interSet = new Set(seqNodeIds.slice(0, -1));
      const kept = eds.filter((e) => {
        if (e.source === nodeId && e.label === item) return false;
        if (interSet.has(e.source) && !e.label) return false;
        return true;
      });

      const newEdges: Edge[] = [];
      // nodeId --[item]--> seq[0]
      newEdges.push({
        id: `${nodeId}-${seqNodeIds[0]}-${item}`,
        source: nodeId, target: seqNodeIds[0],
        label: item, animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: "#6366f1" },
        labelStyle: { fontSize: 11, fontWeight: 600, fill: "#6366f1" },
        labelBgStyle: { fill: "#eef2ff", rx: 4 },
      });
      // seq[i] --> seq[i+1]
      for (let i = 0; i < seqNodeIds.length - 1; i++) {
        newEdges.push({
          id: `${seqNodeIds[i]}-${seqNodeIds[i + 1]}`,
          source: seqNodeIds[i], target: seqNodeIds[i + 1],
          animated: false,
          markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: "#1a5c2e" },
        });
      }

      return [...kept, ...newEdges];
    });
  }, []);

  // ── Right-click swap: first ПКМ marks source, second ПКМ swaps positions + edges ──
  const handleNodeContextMenu = useCallback((e: React.MouseEvent, node: Node) => {
    e.preventDefault();
    e.stopPropagation();
    setSwapSourceId((prev) => {
      if (prev === null) {
        setNodes((ns) => ns.map((n) => ({
          ...n,
          data: { ...n.data, isSwapSource: n.id === node.id },
        })));
        return node.id;
      } else if (prev === node.id) {
        setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, isSwapSource: false } })));
        return null;
      } else {
        const srcId = prev;
        const tgtId = node.id;

        // 1. Swap visual positions
        setNodes((ns) => {
          const srcPos = { ...ns.find((n) => n.id === srcId)!.position };
          const tgtPos = { ...ns.find((n) => n.id === tgtId)!.position };
          return ns.map((n) => {
            if (n.id === srcId) return { ...n, position: tgtPos, data: { ...n.data, isSwapSource: false } };
            if (n.id === tgtId) return { ...n, position: srcPos, data: { ...n.data, isSwapSource: false } };
            return { ...n, data: { ...n.data, isSwapSource: false } };
          });
        });

        // 2. Re-wire edges: swap srcId ↔ tgtId in all edge endpoints
        //    so connections follow the swapped positions
        setEdges((eds) =>
          eds.map((e) => {
            const swapEnd = (id: string) =>
              id === srcId ? tgtId : id === tgtId ? srcId : id;
            const newSource = swapEnd(e.source);
            const newTarget = swapEnd(e.target);
            if (newSource === e.source && newTarget === e.target) return e;
            const newId = `${newSource}-${newTarget}${e.label ? `-${e.label}` : ""}`;
            return { ...e, id: newId, source: newSource, target: newTarget };
          })
        );

        return null;
      }
    });
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Draft recovery banner */}
      {hasDraft && (
        <div className="flex items-center gap-3 px-4 py-1.5 bg-amber-50 border-b border-amber-200 text-xs flex-shrink-0">
          <span className="text-amber-700 font-medium">⚡ Восстановлен черновик после сбоя — изменения не потеряны</span>
          <div className="flex-1" />
          <button
            className="text-amber-600 hover:text-amber-800 underline"
            onClick={() => {
              if (!window.confirm("Сбросить черновик и загрузить последнюю сохранённую версию?")) return;
              try { sessionStorage.removeItem(draftKey); } catch { /* ignore */ }
              const f = getInitialFlow(false);
              const { nodes: rn, edges: re } = flowToRF(f);
              setNodes(rn);
              setEdges(re);
              setStartId(f.startId);
              setSelectedNode(null);
              setHasDraft(false);
            }}
          >
            Сбросить
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b bg-white flex-shrink-0 flex-wrap">
        <span className="text-sm font-semibold text-gray-600 mr-2">+ Добавить шаг:</span>
        {(["date", "number", "choice", "text"] as StepType[]).map((t) => (
          <button
            key={t}
            onClick={() => addStep(t)}
            className="flex items-center gap-1 px-3 py-1.5 text-xs border rounded-lg hover:bg-gray-50 transition-colors"
          >
            {STEP_ICONS[t]} {STEP_LABELS[t]}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="btn-primary flex items-center gap-1.5 text-sm px-4 py-1.5"
        >
          <Save size={14} />
          {saveMutation.isPending ? "Сохранение..." : "Сохранить схему"}
        </button>
      </div>

      {/* Canvas + edit panel */}
      <div className="flex flex-1 overflow-hidden">
        <DictContext.Provider value={{ dictMap, customDictMeta, kindModes }}>
        <div className="flex-1 relative" ref={containerRef}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={NODE_TYPES}
            onNodeClick={(_, node) => { setSelectedNode(node); }}
            onPaneClick={() => { setSelectedNode(null); setSwapSourceId(null); setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, isSwapSource: false } }))); }}
            onNodeContextMenu={handleNodeContextMenu}
            onPaneContextMenu={(e) => e.preventDefault()}
            fitView
            fitViewOptions={{ padding: 0.3 }}
            deleteKeyCode="Delete"
            style={{ background: "#f8fafb" }}
            panOnDrag={[1, 2]}
            selectionOnDrag
            panOnScroll
            zoomOnScroll={false}
            zoomOnDoubleClick={false}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#d1d5db" />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const t = (n.data as unknown as FlowNode).type;
                return t === "start" ? "#22c55e" : t === "confirm" ? "#16a34a" : t === "choice" ? "#a855f7" : t === "date" ? "#3b82f6" : t === "number" ? "#f97316" : "#9ca3af";
              }}
              style={{ background: "#f0f4f0", border: "1px solid #d1d5db" }}
            />
          </ReactFlow>
          <div className="absolute bottom-14 left-3 text-xs text-gray-400 bg-white/80 rounded px-2 py-1 pointer-events-none">
            ЛКМ — переместить узел &nbsp;•&nbsp; Скролл — панорама &nbsp;•&nbsp; ПКМ×1 — выбрать для замены &nbsp;•&nbsp; ПКМ×2 — поменять местами
          </div>
          {swapSourceId && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-orange-500 text-white text-xs font-semibold px-4 py-1.5 rounded-full shadow-lg pointer-events-none animate-pulse">
              🔄 Выбран узел для замены — нажмите ПКМ на другой узел
            </div>
          )}
        </div>

        {selectedNode && (
          <NodeEditPanel
            key={selectedNode.id}
            node={selectedNode}
            allNodes={nodes}
            onUpdate={updateNodeData}
            onDelete={deleteNode}
            onClose={() => setSelectedNode(null)}
            onSetChain={handleSetChain}
          />
        )}
        </DictContext.Provider>
      </div>
    </div>
  );
}

// ─── Dictionary Panels (collapsible) ─────────────────────────────────────
type DictSection = "activities_tech" | "activities_hand" | "locations_field" | "locations_store" | "machine_kinds" | "machine_items" | "crops";

interface Activity { id: number; name: string; grp: string; pos: number; mode?: string | null; options?: string[] | null; message?: string | null }
interface Location  { id: number; name: string; grp: string; pos: number; mode?: string | null; options?: string[] | null; message?: string | null }
interface MachineKind { id: number; title: string; mode: string; pos: number; options?: string[] | null; message?: string | null }
interface MachineItem { id: number; kind_id: number; name: string; pos: number }
interface Crop { name: string; pos: number; mode?: string | null; options?: string[] | null; message?: string | null }
interface CustomDictItem { id: number; dict_id: number; value: string; pos: number; mode?: string | null; options?: string[] | null; message?: string | null }
interface CustomDict { id: number; name: string; pos: number; items: CustomDictItem[] }

const dictApi = {
  all: () => api.get<{ activities: Activity[]; locations: Location[]; machine_kinds: MachineKind[]; machine_items: MachineItem[]; crops: Crop[]; custom_dicts: CustomDict[] }>("/dictionaries").then((r) => r.data),
  addActivity: (b: Omit<Activity, "id">) => api.post("/dictionaries/activities", b).then((r) => r.data),
  delActivity: (id: number) => api.delete(`/dictionaries/activities/${id}`),
  addLocation: (b: Omit<Location, "id">) => api.post("/dictionaries/locations", b).then((r) => r.data),
  delLocation: (id: number) => api.delete(`/dictionaries/locations/${id}`),
  addKind: (b: Omit<MachineKind, "id">) => api.post("/dictionaries/machine-kinds", b).then((r) => r.data),
  updateKind: (id: number, b: Partial<Omit<MachineKind, "id">>) => api.patch(`/dictionaries/machine-kinds/${id}`, b).then((r) => r.data),
  delKind: (id: number) => api.delete(`/dictionaries/machine-kinds/${id}`),
  addItem: (b: Omit<MachineItem, "id">) => api.post("/dictionaries/machine-items", b).then((r) => r.data),
  delItem: (id: number) => api.delete(`/dictionaries/machine-items/${id}`),
  addCrop: (b: { name: string; pos: number }) => api.post("/dictionaries/crops", b).then((r) => r.data),
  delCrop: (name: string) => api.delete(`/dictionaries/crops/${name}`),
  updateActivity: (id: number, b: Partial<Activity>) => api.patch(`/dictionaries/activities/${id}`, b).then((r) => r.data),
  updateLocation: (id: number, b: Partial<Location>) => api.patch(`/dictionaries/locations/${id}`, b).then((r) => r.data),
  updateCrop: (name: string, b: Partial<Crop>) => api.patch(`/dictionaries/crops/${encodeURIComponent(name)}`, b).then((r) => r.data),
  updateCustomItem: (id: number, b: Partial<CustomDictItem>) => api.patch(`/dictionaries/custom/items/${id}`, b).then((r) => r.data),
  addCustomDict: (name: string) => api.post<CustomDict>("/dictionaries/custom", { name, pos: 0 }).then((r) => r.data),
  renameCustomDict: (id: number, name: string) => api.patch(`/dictionaries/custom/${id}`, { name }).then((r) => r.data),
  delCustomDict: (id: number) => api.delete(`/dictionaries/custom/${id}`),
  addCustomItem: (dict_id: number, value: string) => api.post(`/dictionaries/custom/${dict_id}/items`, { dict_id, value, pos: 0 }).then((r) => r.data),
  delCustomItem: (item_id: number) => api.delete(`/dictionaries/custom/items/${item_id}`),
};

// ─── Mode badge config ────────────────────────────────────────────────────
const MODE_META: Record<string, { icon: string; label: string; pill: string }> = {
  list:    { icon: "📋", label: "Список",    pill: "bg-blue-100 text-blue-700" },
  choices: { icon: "🔘", label: "Варианты",  pill: "bg-purple-100 text-purple-700" },
  message: { icon: "💬", label: "Сообщение", pill: "bg-amber-100 text-amber-700" },
};

// ─── Dialog for creating / editing a MachineKind ─────────────────────────
function KindDialog({
  kind,
  onClose,
  onSave,
}: {
  kind: MachineKind | null;
  onClose: () => void;
  onSave: (data: { title: string; mode: string; options?: string[]; message?: string }) => void;
}) {
  const [title, setTitle]     = useState(kind?.title   || "");
  const [mode,  setMode]      = useState(kind?.mode    || "list");
  const [options, setOptions] = useState<string[]>(kind?.options ?? []);
  const [optInput, setOptInput] = useState("");
  const [message, setMessage] = useState(kind?.message || "");

  const addOpt = () => {
    if (!optInput.trim()) return;
    setOptions([...options, optInput.trim()]);
    setOptInput("");
  };

  const submit = () => {
    if (!title.trim()) return;
    onSave({
      title: title.trim(),
      mode,
      options:  mode === "choices" ? options : undefined,
      message:  mode === "message" ? message : undefined,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-[26rem] p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-base">{kind ? "Изменить тип техники" : "Новый тип техники"}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded"><X size={16} /></button>
        </div>

        {/* Name */}
        <div className="mb-3">
          <label className="block text-xs text-gray-500 mb-1">Название</label>
          <input
            className="input"
            placeholder="Трактор, КамАЗ, Комбайн..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            autoFocus
          />
        </div>

        {/* Mode selector */}
        <div className="mb-4">
          <label className="block text-xs text-gray-500 mb-2">Что происходит при выборе этого типа?</label>
          <div className="grid grid-cols-3 gap-2">
            {(["list", "choices", "message"] as const).map((m) => {
              const meta = MODE_META[m];
              return (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`flex flex-col items-center py-3 rounded-xl border-2 text-xs font-medium transition-all ${
                    mode === m
                      ? "border-primary-600 bg-primary-50 text-primary-700"
                      : "border-gray-200 text-gray-600 hover:border-primary-300"
                  }`}
                >
                  <span className="text-xl mb-1">{meta.icon}</span>
                  <span>{meta.label}</span>
                </button>
              );
            })}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {mode === "list"    && "Показывает список единиц (Т-150, Нива…), которые добавляются после создания."}
            {mode === "choices" && "Показывает кнопки выбора из заданных вариантов (без подсписка)."}
            {mode === "message" && "Показывает информационный текст — без дополнительного выбора."}
          </p>
        </div>

        {/* Choices */}
        {mode === "choices" && (
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-1">Варианты выбора</label>
            <div className="space-y-1 mb-1 max-h-40 overflow-y-auto">
              {options.map((opt, i) => (
                <div key={i} className="flex items-center gap-2 bg-purple-50 rounded px-2 py-1">
                  <span className="text-xs flex-1 text-purple-800">{opt}</span>
                  <button onClick={() => setOptions(options.filter((_, j) => j !== i))} className="text-red-400 hover:text-red-600">
                    <X size={11} />
                  </button>
                </div>
              ))}
              {options.length === 0 && (
                <p className="text-xs text-gray-400 italic">Варианты не добавлены</p>
              )}
            </div>
            <div className="flex gap-1">
              <input
                className="border rounded px-2 py-1 text-xs flex-1 outline-none focus:border-primary-500"
                placeholder="Новый вариант..."
                value={optInput}
                onChange={(e) => setOptInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addOpt()}
              />
              <button className="bg-primary-700 text-white px-2 py-1 rounded text-xs hover:bg-primary-800" onClick={addOpt}>+</button>
            </div>
          </div>
        )}

        {/* Message */}
        {mode === "message" && (
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-1">Текст сообщения</label>
            <textarea
              className="input resize-none text-sm"
              rows={3}
              placeholder="Введите текст, который увидит работник…"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>
        )}

        <div className="flex gap-2 mt-2">
          <button className="btn-secondary flex-1" onClick={onClose}>Отмена</button>
          <button
            className="btn-primary flex-1"
            onClick={submit}
            disabled={!title.trim()}
          >
            {kind ? "Сохранить" : "Создать"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Machine Kinds Section (rich) ─────────────────────────────────────────
function MachineKindSection({
  kinds,
  items,
  inv,
  initialOpenDialog = false,
  onDialogOpen,
}: {
  kinds: MachineKind[];
  items: MachineItem[];
  inv: () => void;
  initialOpenDialog?: boolean;
  onDialogOpen?: () => void;
}) {
  const [showDialog, setShowDialog] = useState(false);
  const [editKind, setEditKind]     = useState<MachineKind | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Trigger dialog when parent requests quick-add
  React.useEffect(() => {
    if (initialOpenDialog) {
      setEditKind(null);
      setShowDialog(true);
      onDialogOpen?.();
    }
  }, [initialOpenDialog]);

  const addKind    = useMutation({ mutationFn: (b: Omit<MachineKind, "id">) => dictApi.addKind(b),                            onSuccess: inv });
  const updateKind = useMutation({ mutationFn: ({ id, ...b }: MachineKind) => dictApi.updateKind(id, b),                      onSuccess: inv });
  const delKind    = useMutation({ mutationFn: (id: number) => dictApi.delKind(id),                                           onSuccess: inv });
  const addItem    = useMutation({ mutationFn: (b: Omit<MachineItem, "id">) => dictApi.addItem(b),                            onSuccess: inv });
  const delItem    = useMutation({ mutationFn: (id: number) => dictApi.delItem(id),                                           onSuccess: inv });

  const handleSave = (data: { title: string; mode: string; options?: string[]; message?: string }) => {
    if (editKind) {
      updateKind.mutate({ ...editKind, ...data });
    } else {
      addKind.mutate({ ...data, pos: kinds.length });
    }
    setShowDialog(false);
    setEditKind(null);
  };

  return (
    <div>
      {kinds.map((k) => {
        const kindItems = items.filter((i) => i.kind_id === k.id);
        const meta = MODE_META[k.mode] ?? MODE_META.list;
        const isExpanded = expandedId === k.id;

        return (
          <div key={k.id} className="border border-gray-100 rounded-lg mb-1.5 overflow-hidden">
            {/* Kind header row */}
            <div
              className="flex items-center gap-1.5 px-2 py-1.5 cursor-pointer hover:bg-gray-50 select-none"
              onClick={() => setExpandedId(isExpanded ? null : k.id)}
            >
              <span className="text-gray-400">{isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</span>
              <span className="text-xs font-medium flex-1 truncate">{k.title}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${meta.pill}`}>{meta.icon} {meta.label}</span>
              <button
                onClick={(e) => { e.stopPropagation(); setEditKind(k); setShowDialog(true); }}
                className="p-0.5 rounded hover:bg-blue-100 text-blue-400 hover:text-blue-600 transition-colors"
                title="Изменить"
              >
                <Edit2 size={11} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); if (window.confirm(`Удалить «${k.title}» и все его единицы?`)) delKind.mutate(k.id); }}
                className="p-0.5 rounded hover:bg-red-100 text-red-400 hover:text-red-600 transition-colors"
                title="Удалить"
              >
                <Trash2 size={11} />
              </button>
            </div>

            {/* Expanded content */}
            {isExpanded && (
              <div className="border-t border-gray-100 bg-gray-50 px-3 py-2">
                {k.mode === "list" && (
                  <>
                    {kindItems.length === 0 && (
                      <p className="text-xs text-gray-400 italic mb-1">Нет единиц — добавьте ниже</p>
                    )}
                    {kindItems.map((i) => (
                      <DictRow key={i.id} label={i.name} onDelete={() => delItem.mutate(i.id)} />
                    ))}
                    <MiniAddRow
                      placeholder={`Добавить в «${k.title}»…`}
                      onAdd={(v) => addItem.mutate({ kind_id: k.id, name: v, pos: kindItems.length })}
                    />
                  </>
                )}

                {k.mode === "choices" && (
                  <>
                    {(k.options ?? []).length === 0 ? (
                      <p className="text-xs text-amber-500 mb-1">⚠ Варианты не заданы — нажмите ✎ для редактирования</p>
                    ) : (
                      (k.options ?? []).map((opt, i) => (
                        <div key={i} className="text-xs bg-purple-50 border border-purple-100 rounded px-2 py-1 mb-1 text-purple-700">{opt}</div>
                      ))
                    )}
                    <button
                      className="text-xs text-blue-500 hover:text-blue-700 underline mt-1"
                      onClick={() => { setEditKind(k); setShowDialog(true); }}
                    >
                      ✎ Изменить варианты
                    </button>
                  </>
                )}

                {k.mode === "message" && (
                  <>
                    {k.message ? (
                      <p className="text-xs text-gray-600 italic">{k.message}</p>
                    ) : (
                      <p className="text-xs text-amber-500 mb-1">⚠ Сообщение не задано — нажмите ✎ для редактирования</p>
                    )}
                    <button
                      className="text-xs text-blue-500 hover:text-blue-700 underline mt-1"
                      onClick={() => { setEditKind(k); setShowDialog(true); }}
                    >
                      ✎ Изменить сообщение
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}

      {kinds.length === 0 && (
        <p className="text-xs text-gray-400 italic mb-2">Нет типов — добавьте первый</p>
      )}

      <button
        onClick={() => { setEditKind(null); setShowDialog(true); }}
        className="w-full mt-1 flex items-center justify-center gap-1.5 py-1.5 border border-dashed border-gray-300 rounded-lg text-xs text-gray-500 hover:border-primary-400 hover:text-primary-600 transition-colors"
      >
        <Plus size={12} /> Новый тип техники
      </button>

      {showDialog && (
        <KindDialog
          kind={editKind}
          onClose={() => { setShowDialog(false); setEditKind(null); }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}

function DictRow({ label, onDelete }: { label: React.ReactNode; onDelete: () => void }) {
  return (
    <div className="flex items-center justify-between py-1.5 px-2 hover:bg-gray-50 rounded group">
      <span className="text-xs text-gray-700">{label}</span>
      <button onClick={onDelete} className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-opacity p-0.5">
        <Trash2 size={11} />
      </button>
    </div>
  );
}

// ─── Configurable dict item row (supports mode/options/message) ───────────────
interface DictItemData { name: string; mode?: string | null; options?: string[] | null; message?: string | null }

function ConfigurableDictRow({
  item,
  onDelete,
  onUpdate,
  onRename,
}: {
  item: DictItemData;
  onDelete: () => void;
  onUpdate: (data: { mode?: string | null; options?: string[] | null; message?: string | null }) => void;
  onRename?: (newName: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [mode, setMode] = useState(item.mode || "");
  const [options, setOptions] = useState<string[]>(item.options ?? []);
  const [optInput, setOptInput] = useState("");
  const [message, setMessage] = useState(item.message || "");
  const [editingName, setEditingName] = useState(false);
  const [nameVal, setNameVal] = useState(item.name);
  const hasConfig = !!item.mode;

  React.useEffect(() => {
    setNameVal(item.name);
  }, [item.name]);

  const commitRename = () => {
    const t = nameVal.trim();
    if (!t || t === item.name) {
      setNameVal(item.name);
      setEditingName(false);
      return;
    }
    onRename?.(t);
    setEditingName(false);
  };

  const save = () => {
    onUpdate({
      mode: mode || null,
      options: mode === "choices" ? options : null,
      message: mode === "message" ? message : null,
    });
    setExpanded(false);
  };

  const addOpt = () => {
    if (!optInput.trim()) return;
    setOptions([...options, optInput.trim()]);
    setOptInput("");
  };

  return (
    <div className={`border rounded-lg mb-1 overflow-hidden ${hasConfig ? "border-purple-200" : "border-gray-100"}`}>
      <div className="flex items-center gap-1 px-2 py-1.5 hover:bg-gray-50 group">
        <button type="button" className="text-gray-400 flex-shrink-0" onClick={() => setExpanded(!expanded)}>
          {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </button>
        {editingName ? (
          <input
            className="text-xs flex-1 border border-primary-400 rounded px-1.5 py-0.5 outline-none min-w-0"
            value={nameVal}
            autoFocus
            onChange={(e) => setNameVal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename();
              if (e.key === "Escape") { setNameVal(item.name); setEditingName(false); }
            }}
            onBlur={commitRename}
          />
        ) : (
          <>
            <span className="text-xs text-gray-700 flex-1 truncate">{item.name}</span>
            {onRename && (
              <button
                type="button"
                title="Переименовать"
                className="opacity-0 group-hover:opacity-100 text-primary-500 hover:text-primary-700 p-0.5 flex-shrink-0 transition-opacity"
                onClick={() => { setEditingName(true); setNameVal(item.name); }}
              >
                <Pencil size={11} />
              </button>
            )}
          </>
        )}
        {item.mode === "choices" && (
          <span className="text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded-full font-medium flex-shrink-0">🔘 Варианты</span>
        )}
        {item.mode === "message" && (
          <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium flex-shrink-0">💬 Сообщение</span>
        )}
        <button
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-opacity p-0.5 flex-shrink-0"
        >
          <Trash2 size={11} />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-gray-100 bg-gray-50 px-3 py-2 space-y-2">
          <div>
            <label className="block text-[10px] text-gray-500 mb-1 uppercase tracking-wide">Поведение при выборе</label>
            <div className="flex gap-1.5">
              {[
                { v: "",         label: "Нет" },
                { v: "choices",  label: "🔘 Варианты" },
                { v: "message",  label: "💬 Сообщение" },
              ].map((opt) => (
                <button
                  key={opt.v}
                  onClick={() => setMode(opt.v)}
                  className={`flex-1 py-1 text-[10px] rounded border font-medium transition-colors ${
                    mode === opt.v ? "bg-primary-700 text-white border-primary-700" : "border-gray-200 text-gray-500 hover:border-primary-300"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {mode === "choices" && (
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">Дополнительные варианты</label>
              {options.map((opt, i) => (
                <div key={i} className="flex items-center gap-1 mb-0.5 bg-purple-50 rounded px-2 py-0.5">
                  <span className="text-xs flex-1 text-purple-800">{opt}</span>
                  <button onClick={() => setOptions(options.filter((_, j) => j !== i))} className="text-red-400"><X size={10} /></button>
                </div>
              ))}
              <div className="flex gap-1 mt-1">
                <input className="border rounded px-2 py-0.5 text-xs flex-1 outline-none focus:border-primary-500" placeholder="Добавить вариант..." value={optInput}
                  onChange={(e) => setOptInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addOpt()} />
                <button className="bg-primary-700 text-white px-2 py-0.5 rounded text-xs" onClick={addOpt}>+</button>
              </div>
            </div>
          )}

          {mode === "message" && (
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">Текст сообщения</label>
              <textarea className="border rounded px-2 py-1 text-xs w-full outline-none focus:border-primary-500 resize-none" rows={2}
                placeholder="Введите текст…" value={message} onChange={(e) => setMessage(e.target.value)} />
            </div>
          )}

          <button className="btn-primary w-full py-1 text-xs" onClick={save}>Применить</button>
        </div>
      )}
    </div>
  );
}

function MiniAddRow({ onAdd, placeholder, autoFocus }: { onAdd: (val: string) => void; placeholder?: string; autoFocus?: boolean }) {
  const [v, setV] = useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => { if (autoFocus) inputRef.current?.focus(); }, [autoFocus]);
  return (
    <div className="flex gap-1 mt-1">
      <input
        ref={inputRef}
        className="border rounded px-2 py-1 text-xs flex-1 outline-none focus:border-primary-500"
        placeholder={placeholder || "Новое..."}
        value={v}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && v.trim()) { onAdd(v.trim()); setV(""); } }}
      />
      <button
        className="bg-primary-700 text-white px-2 py-1 rounded text-xs hover:bg-primary-800"
        onClick={() => { if (v.trim()) { onAdd(v.trim()); setV(""); } }}
      >
        +
      </button>
    </div>
  );
}

function DictAccordion() {
  const qc = useQueryClient();
  const [open, setOpen] = useState<DictSection | null>(null);
  const [openCustom, setOpenCustom] = useState<number | null>(null);
  // Which section's input should auto-focus
  const [focusSection, setFocusSection] = useState<DictSection | null>(null);
  const [focusCustom, setFocusCustom] = useState<number | null>(null);
  // Whether to immediately open KindDialog for machine_kinds "+"
  const [kindDialogOpen, setKindDialogOpen] = useState(false);
  // New custom dict dialog
  const [showNewCustom, setShowNewCustom] = useState(false);
  const [newCustomName, setNewCustomName] = useState("");
  // Custom rename
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameVal, setRenameVal] = useState("");

  const { data } = useQuery({ queryKey: ["dict-all"], queryFn: dictApi.all });

  const inv    = () => qc.invalidateQueries({ queryKey: ["dict-all"] });
  const addAct   = useMutation({ mutationFn: (v: { name: string; grp: string }) => dictApi.addActivity({ ...v, pos: 0 }), onSuccess: inv });
  const delAct   = useMutation({ mutationFn: (id: number) => dictApi.delActivity(id), onSuccess: inv });
  const updAct   = useMutation({ mutationFn: ({ id, ...b }: Activity) => dictApi.updateActivity(id, b), onSuccess: inv });
  const addLoc   = useMutation({ mutationFn: (v: { name: string; grp: string }) => dictApi.addLocation({ ...v, pos: 0 }), onSuccess: inv });
  const delLoc   = useMutation({ mutationFn: (id: number) => dictApi.delLocation(id), onSuccess: inv });
  const updLoc   = useMutation({ mutationFn: ({ id, ...b }: Location) => dictApi.updateLocation(id, b), onSuccess: inv });
  const addCrop  = useMutation({ mutationFn: (v: string) => dictApi.addCrop({ name: v, pos: 0 }), onSuccess: inv });
  const delCrop  = useMutation({ mutationFn: (name: string) => dictApi.delCrop(name), onSuccess: inv });
  const updCrop  = useMutation({ mutationFn: ({ name, ...b }: Crop) => dictApi.updateCrop(name, b), onSuccess: inv });
  const renameCrop = useMutation({
    mutationFn: ({ from, to }: { from: string; to: string }) => dictApi.updateCrop(from, { name: to }),
    onSuccess: inv,
    onError: (e: unknown) => {
      const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast("error", typeof d === "string" ? d : "Не удалось переименовать");
    },
  });
  const addCustomDict  = useMutation({ mutationFn: (name: string) => dictApi.addCustomDict(name), onSuccess: (cd: CustomDict) => { inv(); setOpenCustom(cd.id); } });
  const renameCustom   = useMutation({ mutationFn: ({ id, name }: { id: number; name: string }) => dictApi.renameCustomDict(id, name), onSuccess: inv });
  const delCustomDict  = useMutation({ mutationFn: (id: number) => dictApi.delCustomDict(id), onSuccess: inv });
  const addCustomItem  = useMutation({ mutationFn: ({ id, v }: { id: number; v: string }) => dictApi.addCustomItem(id, v), onSuccess: inv });
  const delCustomItem  = useMutation({ mutationFn: (id: number) => dictApi.delCustomItem(id), onSuccess: inv });
  const updCustomItem  = useMutation({ mutationFn: ({ id, ...b }: CustomDictItem) => dictApi.updateCustomItem(id, b), onSuccess: inv });

  const techActs   = data?.activities.filter((a) => a.grp === "техника") ?? [];
  const handActs   = data?.activities.filter((a) => a.grp === "ручная")  ?? [];
  const polya      = data?.locations.filter((l) => l.grp === "поля")     ?? [];
  const sklad      = data?.locations.filter((l) => l.grp === "склад")    ?? [];
  const kinds      = data?.machine_kinds ?? [];
  const items      = data?.machine_items ?? [];
  const crops      = data?.crops ?? [];
  const customDicts = data?.custom_dicts ?? [];

  const quickAdd = (id: DictSection, e: React.MouseEvent) => {
    e.stopPropagation();
    setOpen(id);
    setFocusSection(id);
  };

  const createCustomDict = () => {
    if (!newCustomName.trim()) return;
    addCustomDict.mutate(newCustomName.trim());
    setNewCustomName("");
    setShowNewCustom(false);
  };

  // sections without machine_kinds/items — those get a special rich section
  const sections: { id: DictSection; label: string; addLabel: string; content: React.ReactNode }[] = [
    {
      id: "activities_tech", label: "🚜 Деятельность — Техника", addLabel: "Добавить вид работы (техника)",
      content: (
        <>
          {techActs.map((a) => (
            <ConfigurableDictRow key={a.id} item={{ name: a.name, mode: a.mode, options: a.options, message: a.message }}
              onDelete={() => delAct.mutate(a.id)}
              onUpdate={(b) => updAct.mutate({ ...a, ...b })}
              onRename={(newName) => updAct.mutate({ ...a, name: newName })} />
          ))}
          <MiniAddRow placeholder="Вид деятельности" autoFocus={focusSection === "activities_tech"} onAdd={(v) => { addAct.mutate({ name: v, grp: "техника" }); setFocusSection(null); }} />
        </>
      ),
    },
    {
      id: "activities_hand", label: "🙌 Деятельность — Ручная", addLabel: "Добавить вид работы (ручная)",
      content: (
        <>
          {handActs.map((a) => (
            <ConfigurableDictRow key={a.id} item={{ name: a.name, mode: a.mode, options: a.options, message: a.message }}
              onDelete={() => delAct.mutate(a.id)}
              onUpdate={(b) => updAct.mutate({ ...a, ...b })}
              onRename={(newName) => updAct.mutate({ ...a, name: newName })} />
          ))}
          <MiniAddRow placeholder="Вид ручной работы" autoFocus={focusSection === "activities_hand"} onAdd={(v) => { addAct.mutate({ name: v, grp: "ручная" }); setFocusSection(null); }} />
        </>
      ),
    },
    {
      id: "locations_field", label: "🌾 Поля", addLabel: "Добавить поле",
      content: (
        <>
          {polya.map((l) => (
            <ConfigurableDictRow key={l.id} item={{ name: l.name, mode: l.mode, options: l.options, message: l.message }}
              onDelete={() => delLoc.mutate(l.id)}
              onUpdate={(b) => updLoc.mutate({ ...l, ...b })}
              onRename={(newName) => updLoc.mutate({ ...l, name: newName })} />
          ))}
          <MiniAddRow placeholder="Название поля" autoFocus={focusSection === "locations_field"} onAdd={(v) => { addLoc.mutate({ name: v, grp: "поля" }); setFocusSection(null); }} />
        </>
      ),
    },
    {
      id: "locations_store", label: "🏚 Склад / прочие места", addLabel: "Добавить склад / место",
      content: (
        <>
          {sklad.map((l) => (
            <ConfigurableDictRow key={l.id} item={{ name: l.name, mode: l.mode, options: l.options, message: l.message }}
              onDelete={() => delLoc.mutate(l.id)}
              onUpdate={(b) => updLoc.mutate({ ...l, ...b })}
              onRename={(newName) => updLoc.mutate({ ...l, name: newName })} />
          ))}
          <MiniAddRow placeholder="Название" autoFocus={focusSection === "locations_store"} onAdd={(v) => { addLoc.mutate({ name: v, grp: "склад" }); setFocusSection(null); }} />
        </>
      ),
    },
    {
      id: "crops", label: "🌱 Культуры", addLabel: "Добавить культуру",
      content: (
        <>
          {crops.map((c) => (
            <ConfigurableDictRow key={c.name} item={{ name: c.name, mode: c.mode, options: c.options, message: c.message }}
              onDelete={() => delCrop.mutate(c.name)}
              onUpdate={(b) => updCrop.mutate({ ...c, ...b })}
              onRename={(newName) => renameCrop.mutate({ from: c.name, to: newName.trim() })} />
          ))}
          <MiniAddRow placeholder="Культура" autoFocus={focusSection === "crops"} onAdd={(v) => { addCrop.mutate(v); setFocusSection(null); }} />
        </>
      ),
    },
  ];

  return (
    <div className="border-t border-gray-200">
      <div className="px-3 py-2 text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">
        Словари (справочники)
      </div>

      {/* ── Rich machine kinds section ── */}
      <div className="border-b border-gray-100">
        <div className="flex items-center hover:bg-gray-50">
          <button
            className="flex-1 flex items-center gap-1 px-3 py-2 text-xs font-medium text-gray-700 text-left"
            onClick={() => setOpen(open === "machine_kinds" ? null : "machine_kinds")}
          >
            {open === "machine_kinds" ? <ChevronDown size={12} className="flex-shrink-0" /> : <ChevronRight size={12} className="flex-shrink-0" />}
            <span>⚙️ Типы и единицы техники</span>
          </button>
          <button
            title="Добавить тип техники"
            className="mr-2 p-1 rounded hover:bg-green-100 text-green-600 hover:text-green-800 transition-colors"
            onClick={(e) => { e.stopPropagation(); setOpen("machine_kinds"); setKindDialogOpen(true); }}
          >
            <Plus size={13} />
          </button>
        </div>
        {open === "machine_kinds" && (
          <div className="px-3 pb-3">
            <MachineKindSection kinds={kinds} items={items} inv={inv} initialOpenDialog={kindDialogOpen} onDialogOpen={() => setKindDialogOpen(false)} />
          </div>
        )}
      </div>

      {/* ── Other dict sections ── */}
      {sections.map((s) => (
        <div key={s.id} className="border-b border-gray-100 last:border-0">
          <div className="flex items-center hover:bg-gray-50">
            <button
              className="flex-1 flex items-center gap-1 px-3 py-2 text-xs font-medium text-gray-700 text-left"
              onClick={() => setOpen(open === s.id ? null : s.id)}
            >
              {open === s.id ? <ChevronDown size={12} className="flex-shrink-0" /> : <ChevronRight size={12} className="flex-shrink-0" />}
              <span>{s.label}</span>
            </button>
            <button
              title={s.addLabel}
              className="mr-2 p-1 rounded hover:bg-green-100 text-green-600 hover:text-green-800 transition-colors"
              onClick={(e) => quickAdd(s.id, e)}
            >
              <Plus size={13} />
            </button>
          </div>
          {open === s.id && (
            <div className="px-3 pb-3">{s.content}</div>
          )}
        </div>
      ))}

      {/* ── Custom dict sections ── */}
      {customDicts.map((cd) => (
        <div key={cd.id} className="border-b border-gray-100">
          <div className="flex items-center hover:bg-gray-50">
            <button
              className="flex-1 flex items-center gap-1 px-3 py-2 text-xs font-medium text-gray-700 text-left"
              onClick={() => setOpenCustom(openCustom === cd.id ? null : cd.id)}
            >
              {openCustom === cd.id ? <ChevronDown size={12} className="flex-shrink-0" /> : <ChevronRight size={12} className="flex-shrink-0" />}
              {renamingId === cd.id ? (
                <input
                  className="border rounded px-1 py-0.5 text-xs flex-1 outline-none focus:border-primary-500"
                  value={renameVal}
                  autoFocus
                  onChange={(e) => setRenameVal(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && renameVal.trim()) { renameCustom.mutate({ id: cd.id, name: renameVal.trim() }); setRenamingId(null); }
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                  onBlur={() => { if (renameVal.trim()) renameCustom.mutate({ id: cd.id, name: renameVal.trim() }); setRenamingId(null); }}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span>📂 {cd.name}</span>
              )}
            </button>
            <button
              title="Добавить запись"
              className="mr-0.5 p-1 rounded hover:bg-green-100 text-green-600 hover:text-green-800 transition-colors"
              onClick={(e) => { e.stopPropagation(); setOpenCustom(cd.id); setFocusCustom(cd.id); }}
            >
              <Plus size={13} />
            </button>
            <button
              title="Переименовать"
              className="mr-0.5 p-1 rounded hover:bg-blue-100 text-blue-400 hover:text-blue-600 transition-colors"
              onClick={(e) => { e.stopPropagation(); setRenamingId(cd.id); setRenameVal(cd.name); }}
            >
              <Edit2 size={11} />
            </button>
            <button
              title="Удалить категорию"
              className="mr-2 p-1 rounded hover:bg-red-100 text-red-400 hover:text-red-600 transition-colors"
              onClick={(e) => { e.stopPropagation(); if (window.confirm(`Удалить категорию «${cd.name}» и все её записи?`)) delCustomDict.mutate(cd.id); }}
            >
              <Trash2 size={11} />
            </button>
          </div>
          {openCustom === cd.id && (
            <div className="px-3 pb-3">
              {cd.items.map((i) => (
                <ConfigurableDictRow key={i.id} item={{ name: i.value, mode: i.mode, options: i.options, message: i.message }}
                  onDelete={() => delCustomItem.mutate(i.id)}
                  onUpdate={(b) => updCustomItem.mutate({ ...i, ...b })} />
              ))}
              {cd.items.length === 0 && (
                <p className="text-xs text-gray-400 italic mb-1">Нет записей — добавьте первую</p>
              )}
              <MiniAddRow
                placeholder={`Добавить в «${cd.name}»…`}
                autoFocus={focusCustom === cd.id}
                onAdd={(v) => { addCustomItem.mutate({ id: cd.id, v }); setFocusCustom(null); }}
              />
            </div>
          )}
        </div>
      ))}

      {/* ── Add new custom category button ── */}
      {showNewCustom ? (
        <div className="px-3 py-2 border-t border-gray-100">
          <p className="text-xs text-gray-500 mb-1">Название новой категории:</p>
          <div className="flex gap-1">
            <input
              className="border rounded px-2 py-1 text-xs flex-1 outline-none focus:border-primary-500"
              placeholder="Весовая, Бригада…"
              value={newCustomName}
              onChange={(e) => setNewCustomName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") createCustomDict(); if (e.key === "Escape") setShowNewCustom(false); }}
              autoFocus
            />
            <button className="bg-primary-700 text-white px-2 py-1 rounded text-xs hover:bg-primary-800" onClick={createCustomDict}>+</button>
            <button className="border border-gray-300 text-gray-500 px-2 py-1 rounded text-xs hover:bg-gray-50" onClick={() => setShowNewCustom(false)}>✕</button>
          </div>
        </div>
      ) : (
        <button
          className="w-full flex items-center justify-center gap-1.5 py-2.5 text-xs text-gray-500 hover:text-primary-600 hover:bg-primary-50 transition-colors border-t border-gray-100"
          onClick={() => setShowNewCustom(true)}
        >
          <Plus size={13} />
          Добавить свою категорию
        </button>
      )}
    </div>
  );
}

// ─── New Form Dialog ──────────────────────────────────────────────────────
function NewFormDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: number) => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [roles, setRoles] = useState<string[]>([]);

  const createMut = useMutation({
    mutationFn: () => api.post("/forms", { name, title, roles, schema: { fields: [] } }).then((r) => r.data),
    onSuccess: (form: FormTemplate) => {
      qc.invalidateQueries({ queryKey: ["forms-admin"] });
      toast("success", "Раздел создан!");
      onCreated(form.id);
      onClose();
    },
    onError: (e: any) => toast("error", e?.response?.data?.detail || "Ошибка создания"),
  });

  const toggleRole = (r: string) =>
    setRoles((rs) => rs.includes(r) ? rs.filter((x) => x !== r) : [...rs, r]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-96 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-lg">Новый раздел</h3>
          <button onClick={onClose}><X size={18} /></button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Системное имя (латиница)</label>
            <input className="input" placeholder="my_form" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Заголовок</label>
            <input className="input" placeholder="Мой отчёт" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-2">Роли</label>
            <div className="flex flex-wrap gap-2">
              {ROLES.map((r) => (
                <button
                  key={r}
                  onClick={() => toggleRole(r)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${roles.includes(r) ? "bg-primary-700 text-white border-primary-700" : "border-gray-300 text-gray-600 hover:border-primary-400"}`}
                >
                  {ROLE_LABELS[r]}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-2 mt-5">
          <button className="btn-secondary flex-1" onClick={onClose}>Отмена</button>
          <button
            className="btn-primary flex-1"
            onClick={() => createMut.mutate()}
            disabled={!name.trim() || !title.trim() || createMut.isPending}
          >
            Создать
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────
export default function FormFlowPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showNew, setShowNew] = useState(false);

  const { data: forms = [], isLoading } = useQuery<FormTemplate[]>({
    queryKey: ["forms-admin"],
    queryFn: () => api.get("/forms").then((r) => r.data),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.delete(`/forms/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["forms-admin"] }); setSelectedId(null); toast("success", "Удалено"); },
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      api.patch(`/forms/${id}`, { is_active }),
    // Update cache directly — do NOT refetch (to avoid server filtering out inactive forms)
    onSuccess: (_, { id, is_active }) => {
      qc.setQueryData<FormTemplate[]>(["forms-admin"], (old) =>
        old?.map((f) => f.id === id ? { ...f, is_active } : f) ?? []
      );
    },
  });

  const selectedForm = forms.find((f) => f.id === selectedId);

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Left Panel ── */}
      <aside className="w-64 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="font-bold text-base text-gray-800">Разделы</h2>
            <p className="text-xs text-gray-400">Формы заполнения</p>
          </div>
          <button
            onClick={() => setShowNew(true)}
            className="w-8 h-8 flex items-center justify-center bg-primary-700 text-white rounded-lg hover:bg-primary-800 transition-colors"
            title="Новый раздел"
          >
            <Plus size={16} />
          </button>
        </div>

        {/* Form list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-700" /></div>
          ) : forms.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-xs px-4">
              Нет разделов.<br />Нажмите «+» для создания.
            </div>
          ) : (
            <div className="py-2">
              {forms.map((form) => (
                <div
                  key={form.id}
                  className={`mx-2 mb-1 rounded-lg overflow-hidden ${selectedId === form.id ? "ring-2 ring-primary-500" : ""} ${!form.is_active ? "opacity-60" : ""}`}
                >
                  <button
                    className={`w-full text-left px-3 py-2.5 transition-colors ${selectedId === form.id ? "bg-primary-50" : "hover:bg-gray-50"}`}
                    onClick={() => setSelectedId(form.id)}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`font-medium text-sm truncate ${form.is_active ? "text-gray-800" : "text-gray-400 line-through"}`}>
                        {form.title}
                      </span>
                      <span
                        className={`ml-2 flex-shrink-0 w-2 h-2 rounded-full ${form.is_active ? "bg-green-400" : "bg-gray-300"}`}
                        title={form.is_active ? "Активна (видна в мобильном)" : "Скрыта от работяг"}
                      />
                    </div>
                    <span className="text-xs text-gray-400 font-mono">{form.name}</span>
                    {!form.is_active && (
                      <span className="text-[10px] text-amber-500 font-medium">скрыта от работяг</span>
                    )}
                  </button>
                  {selectedId === form.id && (
                    <div className="flex border-t border-gray-100">
                      <button
                        className={`flex-1 py-1 text-xs text-center transition-colors ${
                          form.is_active
                            ? "hover:bg-amber-50 text-amber-600"
                            : "hover:bg-green-50 text-green-600"
                        }`}
                        onClick={() => {
                          if (form.is_active) {
                            if (!window.confirm(`Скрыть «${form.title}» от работяг в мобильном?\n\nФорма останется видна здесь в панели администратора.`)) return;
                          }
                          toggleActive.mutate({ id: form.id, is_active: !form.is_active });
                        }}
                      >
                        {form.is_active ? "Скрыть от работяг" : "Активировать"}
                      </button>
                      <button
                        className="flex-1 py-1 text-xs text-center hover:bg-red-50 text-red-400 transition-colors border-l border-gray-100"
                        onClick={() => window.confirm(`Удалить «${form.title}»?`) && deleteMut.mutate(form.id)}
                      >
                        Удалить
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Dict accordion */}
          <DictAccordion />
        </div>
      </aside>

      {/* ── Right Panel ── */}
      <main className="flex-1 overflow-hidden flex flex-col">
        {selectedForm ? (
          <ReactFlowProvider>
            <div className="px-4 py-2 border-b bg-white flex items-center gap-3 flex-shrink-0">
              <h2 className="font-bold text-gray-800">{selectedForm.title}</h2>
              <span className="text-xs font-mono text-gray-400">{selectedForm.name}</span>
              {selectedForm.roles.map((r) => (
                <span key={r} className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full text-xs">{ROLE_LABELS[r] || r}</span>
              ))}
            </div>
            <div className="flex-1 overflow-hidden">
              <FlowErrorBoundary>
                <FlowEditor form={selectedForm} onSaved={() => {}} />
              </FlowErrorBoundary>
            </div>
          </ReactFlowProvider>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-400">
              <div className="text-5xl mb-4">🗺</div>
              <p className="font-medium text-gray-600 mb-1">Выберите раздел слева</p>
              <p className="text-sm">или создайте новый нажав «+»</p>
            </div>
          </div>
        )}
      </main>

      {showNew && (
        <NewFormDialog
          onClose={() => setShowNew(false)}
          onCreated={(id) => setSelectedId(id)}
        />
      )}
    </div>
  );
}

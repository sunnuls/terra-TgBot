import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, GripVertical, Edit2, Save, X, Eye } from "lucide-react";
import { api } from "../api/client";
import { toast } from "../components/Toast";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

const FIELD_TYPES = [
  { value: "text", label: "Текст" },
  { value: "number", label: "Число" },
  { value: "date", label: "Дата" },
  { value: "select_one", label: "Один из вариантов" },
  { value: "select_many", label: "Несколько вариантов" },
];

const ROLES = ["user", "brigadier", "tim", "it", "accountant"];
const ROLE_LABELS: Record<string, string> = {
  user: "Сотрудник", brigadier: "Бригадир", tim: "ТИМ", it: "IT", accountant: "Бухгалтер",
};

interface FormField {
  id: string;
  type: string;
  label: string;
  required: boolean;
  source?: string;
  options?: string[];
  min?: number;
  max?: number;
  placeholder?: string;
}

interface FormTemplate {
  id: number;
  name: string;
  title: string;
  schema: { fields: FormField[] };
  is_active: boolean;
  roles: string[];
  created_at: string;
}

export default function FormsBuilderPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<FormTemplate | null>(null);
  const [creating, setCreating] = useState(false);
  const [previewForm, setPreviewForm] = useState<FormTemplate | null>(null);
  const [newForm, setNewForm] = useState({ name: "", title: "", roles: [] as string[] });
  const [fields, setFields] = useState<FormField[]>([]);

  const { data: forms = [], isLoading } = useQuery<FormTemplate[]>({
    queryKey: ["forms-admin"],
    queryFn: () => api.get("/forms").then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: unknown) => api.post("/forms", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["forms-admin"] });
      setCreating(false);
      resetNew();
      toast("success", "Форма создана успешно!");
    },
    onError: (e: any) => toast("error", e?.response?.data?.detail || "Ошибка при создании формы"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: unknown }) => api.patch(`/forms/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["forms-admin"] });
      setEditing(null);
      setCreating(false);
      toast("success", "Форма сохранена!");
    },
    onError: (e: any) => toast("error", e?.response?.data?.detail || "Ошибка при сохранении"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/forms/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["forms-admin"] });
      toast("success", "Форма удалена");
    },
    onError: () => toast("error", "Ошибка при удалении"),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      api.patch(`/forms/${id}`, { is_active }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["forms-admin"] });
      toast("info", vars.is_active ? "Форма активирована" : "Форма скрыта");
    },
  });

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const resetNew = () => { setNewForm({ name: "", title: "", roles: [] }); setFields([]); };

  const addField = () => setFields([...fields, { id: `field_${Date.now()}`, type: "text", label: "Новое поле", required: false }]);

  const updateField = (idx: number, updates: Partial<FormField>) =>
    setFields(fields.map((f, i) => i === idx ? { ...f, ...updates } : f));

  const removeField = (idx: number) => setFields(fields.filter((_, i) => i !== idx));

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setFields((items) => {
        const oldIdx = items.findIndex((f) => f.id === active.id);
        const newIdx = items.findIndex((f) => f.id === over.id);
        return arrayMove(items, oldIdx, newIdx);
      });
    }
  };

  const handleSave = () => {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: { schema: { fields }, roles: newForm.roles, title: newForm.title } });
    } else {
      createMutation.mutate({ ...newForm, schema: { fields } });
    }
  };

  const startEdit = (form: FormTemplate) => {
    setEditing(form);
    setCreating(true);
    setPreviewForm(null);
    setNewForm({ name: form.name, title: form.title, roles: form.roles });
    setFields(form.schema.fields);
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Конструктор форм</h1>
        {!creating && (
          <button
            className="btn-primary flex items-center gap-2"
            onClick={() => { setCreating(true); setEditing(null); setPreviewForm(null); resetNew(); }}
          >
            <Plus size={16} />Новая форма
          </button>
        )}
      </div>

      {creating ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Form meta */}
          <div className="card">
            <h3 className="font-semibold mb-4">{editing ? "Редактировать форму" : "Новая форма"}</h3>

            {!editing && (
              <div className="mb-3">
                <label className="block text-xs text-gray-500 mb-1">Системное имя (латиница)</label>
                <input
                  className="input"
                  value={newForm.name}
                  onChange={(e) => setNewForm({ ...newForm, name: e.target.value })}
                  placeholder="my_form_v1"
                />
              </div>
            )}

            <div className="mb-3">
              <label className="block text-xs text-gray-500 mb-1">Заголовок (отображаемый)</label>
              <input
                className="input"
                value={newForm.title}
                onChange={(e) => setNewForm({ ...newForm, title: e.target.value })}
                placeholder="Мой отчёт"
              />
            </div>

            <div className="mb-4">
              <label className="block text-xs text-gray-500 mb-1">Доступные роли</label>
              <div className="flex flex-wrap gap-2">
                {ROLES.map((r) => (
                  <button
                    key={r}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                      newForm.roles.includes(r)
                        ? "bg-primary-700 text-white border-primary-700"
                        : "bg-white text-gray-600 border-gray-300 hover:border-primary-700"
                    }`}
                    onClick={() =>
                      setNewForm({
                        ...newForm,
                        roles: newForm.roles.includes(r)
                          ? newForm.roles.filter((x) => x !== r)
                          : [...newForm.roles, r],
                      })
                    }
                  >
                    {ROLE_LABELS[r]}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <button className="btn-secondary flex-1" onClick={() => { setCreating(false); setEditing(null); }}>
                <X size={14} className="inline mr-1" />Отмена
              </button>
              <button
                className="btn-primary flex-1"
                onClick={handleSave}
                disabled={
                  !newForm.title ||
                  (!editing && !newForm.name) ||
                  createMutation.isPending ||
                  updateMutation.isPending
                }
              >
                <Save size={14} className="inline mr-1" />
                {editing ? "Сохранить" : "Создать"}
              </button>
            </div>
          </div>

          {/* Field builder */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Поля формы ({fields.length})</h3>
              <div className="flex gap-2">
                {fields.length > 0 && (
                  <button
                    className="btn-secondary text-sm flex items-center gap-1 py-1.5 px-3"
                    onClick={() =>
                      setPreviewForm({
                        id: editing?.id ?? 0,
                        name: newForm.name || "preview",
                        title: newForm.title || "Превью",
                        schema: { fields },
                        is_active: true,
                        roles: newForm.roles,
                        created_at: new Date().toISOString(),
                      })
                    }
                  >
                    <Eye size={14} />Превью
                  </button>
                )}
                <button className="btn-secondary text-sm flex items-center gap-1 py-1.5 px-3" onClick={addField}>
                  <Plus size={14} />Поле
                </button>
              </div>
            </div>

            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={fields.map((f) => f.id)} strategy={verticalListSortingStrategy}>
                <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                  {fields.map((field, idx) => (
                    <SortableFieldEditor
                      key={field.id}
                      field={field}
                      onChange={(u) => updateField(idx, u)}
                      onRemove={() => removeField(idx)}
                    />
                  ))}
                  {fields.length === 0 && (
                    <div className="text-center py-8 text-gray-400 text-sm border-2 border-dashed rounded-lg">
                      Нажмите «+ Поле» для добавления
                    </div>
                  )}
                </div>
              </SortableContext>
            </DndContext>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {isLoading ? (
            <div className="col-span-3 flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-700" />
            </div>
          ) : forms.length === 0 ? (
            <div className="col-span-3 text-center py-12 text-gray-400">
              Нет форм. Создайте первую.
            </div>
          ) : (
            forms.map((form) => (
              <div key={form.id} className="card hover:shadow-md transition-shadow flex flex-col">
                {/* Card header */}
                <div className="flex items-start justify-between mb-2">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold truncate">{form.title}</h3>
                    <p className="text-xs text-gray-400 font-mono mt-0.5 truncate">{form.name}</p>
                  </div>
                  <button
                    onClick={() => toggleActiveMutation.mutate({ id: form.id, is_active: !form.is_active })}
                    className={`ml-2 flex-shrink-0 px-2 py-0.5 rounded-full text-xs font-medium transition-colors ${
                      form.is_active
                        ? "bg-green-100 text-green-700 hover:bg-green-200"
                        : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                    }`}
                  >
                    {form.is_active ? "Активна" : "Скрыта"}
                  </button>
                </div>

                {/* Roles */}
                {form.roles.length > 0 ? (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {form.roles.map((r) => (
                      <span key={r} className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">
                        {ROLE_LABELS[r] || r}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-amber-500 mb-2">⚠ Роли не назначены</p>
                )}

                {/* Fields preview summary */}
                <div className="mb-3 flex-1">
                  <p className="text-xs text-gray-500 font-medium mb-1">
                    {form.schema.fields.length} {form.schema.fields.length === 1 ? "поле" : form.schema.fields.length < 5 ? "поля" : "полей"}:
                  </p>
                  <div className="space-y-0.5">
                    {form.schema.fields.slice(0, 4).map((f, i) => (
                      <div key={i} className="flex items-center gap-1.5 text-xs text-gray-500">
                        <span className="w-1.5 h-1.5 rounded-full bg-gray-300 flex-shrink-0" />
                        <span className="truncate">{f.label}</span>
                        <span className="text-gray-300 flex-shrink-0">
                          {f.type === "text" ? "Текст" :
                           f.type === "number" ? "Число" :
                           f.type === "date" ? "Дата" :
                           f.type === "select_one" ? "Выбор" :
                           f.type === "select_many" ? "Мн.выбор" : f.type}
                        </span>
                        {f.required && <span className="text-red-400 flex-shrink-0">*</span>}
                      </div>
                    ))}
                    {form.schema.fields.length > 4 && (
                      <p className="text-xs text-gray-400 pl-3">
                        + ещё {form.schema.fields.length - 4} полей
                      </p>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 mt-auto pt-2 border-t border-gray-100">
                  <button
                    className="flex-1 py-1.5 text-sm flex items-center justify-center gap-1 text-primary-700 hover:bg-primary-50 rounded-lg transition-colors"
                    onClick={() => setPreviewForm(form)}
                  >
                    <Eye size={13} />Превью
                  </button>
                  <button
                    className="flex-1 py-1.5 text-sm flex items-center justify-center gap-1 btn-secondary"
                    onClick={() => startEdit(form)}
                  >
                    <Edit2 size={13} />Изменить
                  </button>
                  <button
                    className="p-2 text-red-400 hover:bg-red-50 rounded-lg transition-colors"
                    onClick={() => window.confirm(`Удалить форму «${form.title}»?`) && deleteMutation.mutate(form.id)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Preview Modal */}
      {previewForm && (
        <FormPreviewModal form={previewForm} onClose={() => setPreviewForm(null)} />
      )}
    </div>
  );
}

/* ─── Form Preview Modal ─────────────────────────────────────────────── */
function FormPreviewModal({ form, onClose }: { form: FormTemplate; onClose: () => void }) {
  const [values, setValues] = useState<Record<string, any>>({});

  const setValue = (id: string, val: any) => setValues((prev) => ({ ...prev, [id]: val }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] flex flex-col">
        {/* Modal header */}
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div>
            <h2 className="font-bold text-lg">{form.title}</h2>
            <p className="text-xs text-gray-400 font-mono">{form.name}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-xl transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Roles badge */}
        {form.roles.length > 0 && (
          <div className="px-5 pt-3 flex flex-wrap gap-1">
            {form.roles.map((r) => (
              <span key={r} className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full text-xs">
                {({ user: "Сотрудник", brigadier: "Бригадир", tim: "ТИМ", it: "IT", accountant: "Бухгалтер" } as any)[r] || r}
              </span>
            ))}
          </div>
        )}

        {/* Form fields */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {form.schema.fields.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <p>Форма не содержит полей.</p>
              <p className="text-sm mt-1">Добавьте поля в редакторе.</p>
            </div>
          ) : (
            form.schema.fields.map((field) => (
              <PreviewField
                key={field.id}
                field={field}
                value={values[field.id]}
                onChange={(v) => setValue(field.id, v)}
              />
            ))
          )}
        </div>

        {/* Submit button (non-functional — just preview) */}
        {form.schema.fields.length > 0 && (
          <div className="px-5 pb-5 pt-3 border-t">
            <button
              className="w-full btn-primary py-3 text-base"
              onClick={() => {
                const missing = form.schema.fields.filter((f) => f.required && !values[f.id]);
                if (missing.length > 0) {
                  toast("error", `Заполните обязательные поля: ${missing.map((f) => f.label).join(", ")}`);
                } else {
                  toast("success", "Превью: форма заполнена корректно ✓");
                }
              }}
            >
              Отправить отчёт
            </button>
            <p className="text-center text-xs text-gray-400 mt-2">
              Это превью — данные не сохраняются
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Preview Field Renderer ─────────────────────────────────────────── */
function PreviewField({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: any;
  onChange: (v: any) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {field.label}
        {field.required && <span className="text-red-500 ml-1">*</span>}
      </label>

      {field.type === "text" && (
        <input
          className="input"
          placeholder={field.placeholder || `Введите ${field.label.toLowerCase()}...`}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {field.type === "number" && (
        <input
          className="input"
          type="number"
          placeholder="0"
          min={field.min}
          max={field.max}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value === "" ? "" : e.target.valueAsNumber)}
        />
      )}

      {field.type === "date" && (
        <input
          className="input"
          type="date"
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {field.type === "select_one" && (
        <div className="space-y-2">
          {(field.options || []).length === 0 ? (
            <p className="text-xs text-amber-500">⚠ Нет вариантов ответа</p>
          ) : (
            (field.options || []).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => onChange(opt)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 border rounded-xl cursor-pointer transition-colors text-left ${
                  value === opt
                    ? "border-primary-700 bg-primary-50 text-primary-700"
                    : "border-gray-200 hover:border-primary-300 hover:bg-gray-50"
                }`}
              >
                <div
                  className={`w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center ${
                    value === opt ? "border-primary-700" : "border-gray-300"
                  }`}
                >
                  {value === opt && <div className="w-2 h-2 rounded-full bg-primary-700" />}
                </div>
                <span className="text-sm">{opt}</span>
              </button>
            ))
          )}
        </div>
      )}

      {field.type === "select_many" && (
        <div className="space-y-2">
          {(field.options || []).length === 0 ? (
            <p className="text-xs text-amber-500">⚠ Нет вариантов ответа</p>
          ) : (
            (field.options || []).map((opt) => {
              const selected: string[] = value || [];
              const isSelected = selected.includes(opt);
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() =>
                    onChange(
                      isSelected
                        ? selected.filter((x) => x !== opt)
                        : [...selected, opt]
                    )
                  }
                  className={`w-full flex items-center gap-3 px-3 py-2.5 border rounded-xl cursor-pointer transition-colors text-left ${
                    isSelected
                      ? "border-primary-700 bg-primary-50 text-primary-700"
                      : "border-gray-200 hover:border-primary-300 hover:bg-gray-50"
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center ${
                      isSelected ? "border-primary-700 bg-primary-700" : "border-gray-300"
                    }`}
                  >
                    {isSelected && (
                      <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                        <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                  <span className="text-sm">{opt}</span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Sortable wrapper ───────────────────────────────────────────────── */
function SortableFieldEditor(props: {
  field: FormField;
  onChange: (u: Partial<FormField>) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: props.field.id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : undefined,
  };

  return (
    <div ref={setNodeRef} style={style}>
      <FieldEditor {...props} dragHandleProps={{ ...attributes, ...listeners }} />
    </div>
  );
}

/* ─── Field Editor (in builder) ──────────────────────────────────────── */
function FieldEditor({
  field,
  onChange,
  onRemove,
  dragHandleProps,
}: {
  field: FormField;
  onChange: (u: Partial<FormField>) => void;
  onRemove: () => void;
  dragHandleProps?: React.HTMLAttributes<HTMLButtonElement>;
}) {
  const [optInput, setOptInput] = useState("");

  return (
    <div className="border border-gray-200 rounded-xl p-3 bg-gray-50">
      <div className="flex items-center gap-2 mb-2">
        <button
          type="button"
          className="cursor-grab active:cursor-grabbing p-0.5 text-gray-300 hover:text-gray-500 flex-shrink-0 touch-none"
          title="Перетащить для изменения порядка"
          {...dragHandleProps}
        >
          <GripVertical size={16} />
        </button>
        <input
          className="input flex-1 text-sm py-1.5"
          value={field.label}
          onChange={(e) => onChange({ label: e.target.value })}
          placeholder="Название поля"
        />
        <select
          className="input text-sm py-1.5 w-40"
          value={field.type}
          onChange={(e) => onChange({ type: e.target.value })}
        >
          {FIELD_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <button onClick={onRemove} className="p-1 text-red-400 hover:text-red-600">
          <Trash2 size={13} />
        </button>
      </div>

      <div className="flex items-center gap-4 text-xs text-gray-500">
        <label className="flex items-center gap-1 cursor-pointer">
          <input
            type="checkbox"
            checked={field.required}
            onChange={(e) => onChange({ required: e.target.checked })}
            className="accent-primary-700"
          />
          Обязательное
        </label>
        {field.type === "number" && (
          <>
            <input
              className="input w-16 text-xs py-1"
              type="number"
              placeholder="min"
              value={field.min ?? ""}
              onChange={(e) => onChange({ min: e.target.valueAsNumber })}
            />
            <input
              className="input w-16 text-xs py-1"
              type="number"
              placeholder="max"
              value={field.max ?? ""}
              onChange={(e) => onChange({ max: e.target.valueAsNumber })}
            />
          </>
        )}
      </div>

      {(field.type === "select_one" || field.type === "select_many") && (
        <div className="mt-2">
          <div className="flex gap-1 mb-1">
            <input
              className="input text-xs py-1 flex-1"
              placeholder="Добавить вариант..."
              value={optInput}
              onChange={(e) => setOptInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && optInput.trim()) {
                  onChange({ options: [...(field.options || []), optInput.trim()] });
                  setOptInput("");
                }
              }}
            />
            <button
              className="btn-secondary text-xs py-1 px-2"
              onClick={() => {
                if (optInput.trim()) {
                  onChange({ options: [...(field.options || []), optInput.trim()] });
                  setOptInput("");
                }
              }}
            >
              +
            </button>
          </div>
          <div className="flex flex-wrap gap-1">
            {(field.options || []).map((opt, i) => (
              <span key={i} className="flex items-center gap-1 bg-white border rounded px-2 py-0.5 text-xs">
                {opt}
                <button
                  onClick={() => onChange({ options: (field.options || []).filter((_, j) => j !== i) })}
                  className="text-red-400"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

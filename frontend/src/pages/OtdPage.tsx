import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { PixelPanel } from "../ui/PixelPanel";
import { PixelButton } from "../ui/PixelButton";
import { PixelIcon } from "../ui/PixelIcon";

type Dicts = {
  activities?: { tech?: string[]; hand?: string[] };
  locations?: { fields?: string[]; ware?: string[] };
  crops?: string[];
};

type Draft = {
  step: number;

  dateMode: "today" | "yesterday" | "custom";
  work_date: string; // YYYY-MM-DD

  shift?: "day" | "night" | "custom";
  shift_custom?: string;

  location: string;
  location_grp: "fields" | "ware";
  favorites: string[];
  location_query: string;

  work_grp: "tech" | "hand";
  activity: string;

  hours: number;
  people?: number;
  rows?: number;

  comment?: string;
};

const DRAFT_KEY = "terra_otd_draft_v1";
const LAST_KEY = "terra_otd_last_v1";
const FAV_KEY = "terra_otd_favs_v1";

function isoDate(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

function loadJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function saveJson(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore
  }
}

function defaultDraft(): Draft {
  const today = new Date();
  return {
    step: 1,
    dateMode: "today",
    work_date: isoDate(today),
    shift: "day",
    location: "",
    location_grp: "fields",
    favorites: [],
    location_query: "",
    work_grp: "hand",
    activity: "",
    hours: 8,
    people: 1,
    rows: 0,
    comment: "",
  };
}

function stepTitle(step: number): string {
  switch (step) {
    case 1:
      return "Дата";
    case 2:
      return "Смена";
    case 3:
      return "Локация";
    case 4:
      return "Вид работы";
    case 5:
      return "Часы / люди / ряды";
    case 6:
      return "Комментарий";
    case 7:
      return "Отправка";
    default:
      return "ОТД";
  }
}

export function OtdPage() {
  const [dicts, setDicts] = useState<Dicts | null>(null);
  const [draft, setDraft] = useState<Draft>(() => {
    const base = defaultDraft();
    const saved = loadJson<Draft>(DRAFT_KEY);
    const last = loadJson<Partial<Draft>>(LAST_KEY);
    const favs = loadJson<string[]>(FAV_KEY) || [];

    // Prefill order: saved draft > last report > defaults
    const merged: Draft = {
      ...base,
      ...(last || {}),
      ...(saved || {}),
      favorites: Array.isArray((saved as any)?.favorites)
        ? (saved as any).favorites
        : Array.isArray((last as any)?.favorites)
          ? (last as any).favorites
          : favs,
    };

    merged.step = clamp(Number((saved as any)?.step ?? 1), 1, 7);
    merged.hours = clamp(Number(merged.hours || 0), 1, 24);
    return merged;
  });

  const [submitStatus, setSubmitStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [submitError, setSubmitError] = useState<string>("");

  const autosaveTimer = useRef<number | null>(null);

  // Load dictionaries once
  useEffect(() => {
    let cancelled = false;
    api
      .dictionaries()
      .then((d) => {
        if (!cancelled) setDicts(d as Dicts);
      })
      .catch(() => {
        if (!cancelled) setDicts({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Autosave draft (debounced)
  useEffect(() => {
    if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current);
    autosaveTimer.current = window.setTimeout(() => {
      saveJson(DRAFT_KEY, draft);
      saveJson(FAV_KEY, draft.favorites);
    }, 250);
    return () => {
      if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current);
    };
  }, [draft]);

  const step = clamp(draft.step, 1, 7);

  const locationsAll = useMemo(() => {
    const f = dicts?.locations?.fields || [];
    const w = dicts?.locations?.ware || [];
    return {
      fields: f,
      ware: w,
    };
  }, [dicts]);

  const filteredLocations = useMemo(() => {
    const list = draft.location_grp === "ware" ? locationsAll.ware : locationsAll.fields;
    const q = (draft.location_query || "").trim().toLowerCase();
    if (!q) return list;
    return list.filter((x: string) => x.toLowerCase().includes(q));
  }, [draft.location_grp, draft.location_query, locationsAll.fields, locationsAll.ware]);

  const favoriteSet = useMemo(() => new Set(draft.favorites || []), [draft.favorites]);
  const favoriteLocations = useMemo(() => {
    const list = [...(draft.favorites || [])];
    return list;
  }, [draft.favorites]);

  const activityList = useMemo(() => {
    if (draft.work_grp === "tech") return dicts?.activities?.tech || [];
    return dicts?.activities?.hand || [];
  }, [dicts, draft.work_grp]);

  const canNext = useMemo(() => {
    if (step === 1) return !!draft.work_date;
    if (step === 2) return true;
    if (step === 3) return (draft.location || "").trim().length > 0;
    if (step === 4) return (draft.activity || "").trim().length > 0;
    if (step === 5) return draft.hours >= 1 && draft.hours <= 24;
    if (step === 6) return true;
    return true;
  }, [draft, step]);

  const goStep = (n: number) => setDraft((d: Draft) => ({ ...d, step: clamp(n, 1, 7) }));
  const next = () => canNext && goStep(step + 1);
  const back = () => goStep(step - 1);

  const setDateMode = (mode: Draft["dateMode"]) => {
    const now = new Date();
    if (mode === "today") {
      setDraft((d: Draft) => ({ ...d, dateMode: mode, work_date: isoDate(now) }));
      return;
    }
    if (mode === "yesterday") {
      const y = new Date(now);
      y.setDate(now.getDate() - 1);
      setDraft((d: Draft) => ({ ...d, dateMode: mode, work_date: isoDate(y) }));
      return;
    }
    setDraft((d: Draft) => ({ ...d, dateMode: mode }));
  };

  const toggleFavorite = (loc: string) => {
    setDraft((d: Draft) => {
      const set = new Set(d.favorites || []);
      if (set.has(loc)) set.delete(loc);
      else set.add(loc);
      return { ...d, favorites: [...set] };
    });
  };

  const submit = async () => {
    setSubmitStatus("loading");
    setSubmitError("");
    try {
      // We do NOT change backend report logic: send only fields backend understands.
      // Extra fields (people/rows/comment/shift) are stored locally for now.
      const payload: any = {
        work_date: draft.work_date,
        hours: Number(draft.hours),
        location: draft.location,
        location_grp: draft.location_grp === "ware" ? "склад" : "поля",
        activity: draft.activity,
        act_grp: draft.work_grp === "tech" ? "техника" : "ручная",
        // Extra properties: backend should ignore unknown keys, report logic remains the same.
        comment: (draft.comment || "").trim() || undefined,
        people: draft.people ?? undefined,
        rows: draft.rows ?? undefined,
        shift: draft.shift || undefined,
        shift_custom: (draft.shift_custom || "").trim() || undefined,
      };

      const res = await api.createReport(payload);
      // Save as last successful
      saveJson(LAST_KEY, {
        dateMode: "today",
        work_date: draft.work_date,
        location: draft.location,
        location_grp: draft.location_grp,
        work_grp: draft.work_grp,
        activity: draft.activity,
        hours: draft.hours,
        favorites: draft.favorites,
      });
      // Clear draft
      saveJson(DRAFT_KEY, null);
      setDraft((d: Draft) => ({ ...defaultDraft(), favorites: d.favorites || [], step: 7 }));
      setSubmitStatus("success");
      // small delay then go home
      window.setTimeout(() => {
        setSubmitStatus("idle");
      }, 1200);
      return res;
    } catch (e: any) {
      setSubmitStatus("error");
      setSubmitError(String(e?.message || e));
    }
  };

  return (
    <div className="container">
      <div className="pxUI">
        <PixelPanel title={`ОТД — ${stepTitle(step)}`}>
          <div className="pxStepbar" aria-hidden="true">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className={`pxStepDot ${i + 1 === step ? "pxStepDot--active" : ""}`.trim()} />
            ))}
          </div>

          <div style={{ height: 10 }} />

          {step === 1 ? (
            <div className="pxForm">
              <div className="pxField">
                <div className="pxLabel">Выбор даты</div>
                <div className="pxPills">
                  <button
                    className={`pxPill ${draft.dateMode === "today" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDateMode("today")}
                  >
                    Сегодня
                  </button>
                  <button
                    className={`pxPill ${draft.dateMode === "yesterday" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDateMode("yesterday")}
                  >
                    Вчера
                  </button>
                  <button
                    className={`pxPill ${draft.dateMode === "custom" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDateMode("custom")}
                  >
                    Своя дата
                  </button>
                </div>
              </div>

              {draft.dateMode === "custom" ? (
                <div className="pxField">
                  <div className="pxLabel">Дата</div>
                  <input
                    className="pxInput"
                    type="date"
                    value={draft.work_date}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setDraft((d: Draft) => ({ ...d, work_date: e.target.value }))
                    }
                  />
                </div>
              ) : null}
            </div>
          ) : null}

          {step === 2 ? (
            <div className="pxForm">
              <div className="pxField">
                <div className="pxLabel">Смена (опционально)</div>
                <div className="pxPills">
                  <button
                    className={`pxPill ${draft.shift === "day" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDraft((d) => ({ ...d, shift: "day" }))}
                  >
                    Дневная
                  </button>
                  <button
                    className={`pxPill ${draft.shift === "night" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDraft((d) => ({ ...d, shift: "night" }))}
                  >
                    Ночная
                  </button>
                  <button
                    className={`pxPill ${draft.shift === "custom" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDraft((d) => ({ ...d, shift: "custom" }))}
                  >
                    Другая
                  </button>
                </div>
                {draft.shift === "custom" ? (
                  <input
                    className="pxInput"
                    placeholder="Например: 2-я"
                    value={draft.shift_custom || ""}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setDraft((d: Draft) => ({ ...d, shift_custom: e.target.value }))
                    }
                  />
                ) : null}
                <div className="pxHint">Смена не отправляется в бэкенд (пока нет поля). Хранится локально.</div>
              </div>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="pxForm">
              <div className="pxField">
                <div className="pxLabel">Группа локаций</div>
                <div className="pxPills">
                  <button
                    className={`pxPill ${draft.location_grp === "fields" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDraft((d) => ({ ...d, location_grp: "fields" }))}
                  >
                    Поля
                  </button>
                  <button
                    className={`pxPill ${draft.location_grp === "ware" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDraft((d) => ({ ...d, location_grp: "ware" }))}
                  >
                    Склад
                  </button>
                </div>
              </div>

              <div className="pxField">
                <div className="pxLabel">Поиск</div>
                <input
                  className="pxInput"
                  placeholder="Введите для поиска…"
                  value={draft.location_query}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setDraft((d: Draft) => ({ ...d, location_query: e.target.value }))
                  }
                />
              </div>

              {favoriteLocations.length > 0 ? (
                <div className="pxField">
                  <div className="pxLabel">Избранное</div>
                  <div className="pxPills">
                    {favoriteLocations.map((loc) => (
                      <button
                        key={loc}
                        className={`pxPill ${draft.location === loc ? "pxPill--active" : ""}`}
                        type="button"
                        onClick={() => setDraft((d: Draft) => ({ ...d, location: loc }))}
                      >
                        {loc}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="pxField">
                <div className="pxLabel">Список</div>
                <div className="pxButtonList">
                  {filteredLocations.slice(0, 18).map((loc: string) => (
                    <div key={loc}>
                      <PixelButton
                        title={loc}
                        subtitle={favoriteSet.has(loc) ? "★ в избранном" : "добавить в избранное"}
                        left={<PixelIcon name="otd" />}
                        onClick={() => setDraft((d: Draft) => ({ ...d, location: loc }))}
                      />
                    </div>
                  ))}
                </div>
                <div className="pxHint">Тап по кнопке выбирает локацию. Долгое нажатие пока не используем.</div>
              </div>

              {draft.location ? (
                <div className="pxRow">
                  <button
                    className={`pxPill ${favoriteSet.has(draft.location) ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => toggleFavorite(draft.location)}
                  >
                    {favoriteSet.has(draft.location) ? "★ Убрать из избранного" : "☆ В избранное"}
                  </button>
                  <button className="pxPill pxPill--active" type="button" onClick={next}>
                    Выбрать: {draft.location}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          {step === 4 ? (
            <div className="pxForm">
              <div className="pxField">
                <div className="pxLabel">Тип работы</div>
                <div className="pxPills">
                  <button
                    className={`pxPill ${draft.work_grp === "hand" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDraft((d) => ({ ...d, work_grp: "hand", activity: "" }))}
                  >
                    Ручная
                  </button>
                  <button
                    className={`pxPill ${draft.work_grp === "tech" ? "pxPill--active" : ""}`}
                    type="button"
                    onClick={() => setDraft((d) => ({ ...d, work_grp: "tech", activity: "" }))}
                  >
                    Техника
                  </button>
                </div>
              </div>

              <div className="pxField">
                <div className="pxLabel">Вид работы</div>
                <div className="pxPills">
                  {activityList.slice(0, 18).map((a) => (
                    <button
                      key={a}
                      className={`pxPill ${draft.activity === a ? "pxPill--active" : ""}`}
                      type="button"
                      onClick={() => setDraft((d) => ({ ...d, activity: a }))}
                    >
                      {a}
                    </button>
                  ))}
                </div>
                <div className="pxHint">Справочник загружается из /api/dictionaries.</div>
              </div>
            </div>
          ) : null}

          {step === 5 ? (
            <div className="pxForm">
              <div className="pxField">
                <div className="pxLabel">Часы (1..24)</div>
                <input
                  className="pxInput"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={24}
                  value={draft.hours}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setDraft((d: Draft) => ({ ...d, hours: clamp(Number(e.target.value || 0), 1, 24) }))
                  }
                />
                <div className="pxHint">Сервер проверяет лимит 24 часа в сутки (как в боте).</div>
              </div>

              <div className="pxRow">
                <div className="pxField">
                  <div className="pxLabel">Люди (опц.)</div>
                  <input
                    className="pxInput"
                    type="number"
                    inputMode="numeric"
                    min={0}
                    value={draft.people ?? 0}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setDraft((d: Draft) => ({ ...d, people: clamp(Number(e.target.value || 0), 0, 999) }))
                    }
                  />
                </div>
                <div className="pxField">
                  <div className="pxLabel">Ряды (опц.)</div>
                  <input
                    className="pxInput"
                    type="number"
                    inputMode="numeric"
                    min={0}
                    value={draft.rows ?? 0}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setDraft((d: Draft) => ({ ...d, rows: clamp(Number(e.target.value || 0), 0, 99999) }))
                    }
                  />
                </div>
              </div>
              <div className="pxHint">Поля люди/ряды пока не отправляются в бэкенд (нет полей). Хранятся как черновик.</div>
            </div>
          ) : null}

          {step === 6 ? (
            <div className="pxForm">
              <div className="pxField">
                <div className="pxLabel">Комментарий (опционально)</div>
                <input
                  className="pxInput"
                  placeholder="Например: доп. информация"
                  value={draft.comment || ""}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setDraft((d: Draft) => ({ ...d, comment: e.target.value }))
                  }
                />
                <div className="pxHint">Комментарий пока не отправляется в бэкенд (нет поля). Сохраняем локально.</div>
              </div>
            </div>
          ) : null}

          {step === 7 ? (
            <div className="pxForm">
              <div className="pxField">
                <div className="pxLabel">Проверьте данные</div>
                <div className="pxHint">
                  Дата: {draft.work_date}
                  <br />
                  Локация: {draft.location} ({draft.location_grp})
                  <br />
                  Работа: {draft.activity} ({draft.work_grp})
                  <br />
                  Часы: {draft.hours}
                </div>
              </div>

              {submitStatus === "error" ? <div className="pxHint">Ошибка: {submitError}</div> : null}
              {submitStatus === "success" ? <div className="pxHint">✅ Отправлено</div> : null}

              <PixelButton
                title={submitStatus === "loading" ? "Отправка…" : "Отправить"}
                subtitle="Запись будет сохранена в БД"
                left={<PixelIcon name="otd" />}
                onClick={submitStatus === "loading" ? undefined : submit}
                disabled={submitStatus === "loading"}
              />
            </div>
          ) : null}

          <div style={{ height: 12 }} />

          <div className="pxRow">
            <button className="pxPill" type="button" onClick={back} disabled={step <= 1}>
              Назад
            </button>
            <button className={`pxPill ${canNext ? "pxPill--active" : ""}`} type="button" onClick={next} disabled={!canNext || step >= 7}>
              Далее
            </button>
          </div>
        </PixelPanel>
      </div>
    </div>
  );
}

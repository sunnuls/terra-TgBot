import { api } from "./client";

export interface Report {
  id: number;
  created_at: string;
  user_id: number | null;
  reg_name: string | null;
  work_date: string | null;
  hours: number | null;
  location: string | null;
  location_grp: string | null;
  activity: string | null;
  activity_grp: string | null;
  machine_type: string | null;
  machine_name: string | null;
  crop: string | null;
  trips: number | null;
}

export interface ReportCreate {
  work_date: string;
  hours: number;
  location: string;
  location_grp: string;
  activity: string;
  activity_grp: string;
  machine_type?: string;
  machine_name?: string;
  crop?: string;
  trips?: number;
}

export interface BrigReport {
  id: number;
  work_date: string | null;
  work_type: string | null;
  field: string | null;
  shift: string | null;
  rows: number | null;
  bags: number | null;
  workers: number | null;
  created_at: string;
}

export interface BrigReportCreate {
  work_date: string;
  work_type: string;
  field: string;
  shift: string;
  rows: number;
  bags: number;
  workers: number;
}

interface DictItemModes { mode?: string | null; options?: string[] | null; message?: string | null }

export interface Dictionaries {
  activities: ({ id: number; name: string; grp: string; pos: number } & DictItemModes)[];
  locations:  ({ id: number; name: string; grp: string; pos: number } & DictItemModes)[];
  machine_kinds: { id: number; title: string; mode: string; pos: number; options?: string[] | null; message?: string | null }[];
  machine_items: { id: number; kind_id: number; name: string; pos: number }[];
  crops: ({ name: string; pos: number } & DictItemModes)[];
  custom_dicts: { id: number; name: string; pos: number; items: ({ id: number; dict_id: number; value: string; pos: number } & DictItemModes)[] }[];
}

export interface Stats {
  period: string;
  total_hours: number;
  report_count: number;
  days_worked: number;
}

/** ОТД: классика или flow-форма «otd» */
export interface ReportFeedItem extends Report {
  source: "otd" | "form";
  form_title?: string | null;
}

export interface FormResponse {
  id: number;
  form_id: number;
  user_id: number;
  data: Record<string, string>;
  submitted_at: string;
}

export const reportsApi = {
  getDictionaries: () => api.get<Dictionaries>("/dictionaries").then((r) => r.data),

  createReport: (data: ReportCreate) =>
    api.post<Report>("/reports", data).then((r) => r.data),

  listReports: (params?: { date_from?: string; date_to?: string; limit?: number }) =>
    api.get<Report[]>("/reports", { params }).then((r) => r.data),

  /** ОТД + flow «otd» в одном списке */
  listOtdFeed: (params?: { limit?: number }) =>
    api.get<ReportFeedItem[]>("/reports/feed", { params }).then((r) => r.data),

  getReport: (id: number) => api.get<Report>(`/reports/${id}`).then((r) => r.data),

  getFormResponse: (id: number) =>
    api.get<FormResponse>(`/form-responses/${id}`).then((r) => r.data),

  updateReport: (id: number, data: Partial<ReportCreate>) =>
    api.patch<Report>(`/reports/${id}`, data).then((r) => r.data),

  deleteReport: (id: number) => api.delete(`/reports/${id}`),

  updateBrigReport: (id: number, data: Partial<BrigReportCreate>) =>
    api.patch<BrigReport>(`/brig/reports/${id}`, data).then((r) => r.data),

  createBrigReport: (data: BrigReportCreate) =>
    api.post<BrigReport>("/brig/reports", data).then((r) => r.data),

  listBrigReports: (params?: { date_from?: string; date_to?: string }) =>
    api.get<BrigReport[]>("/brig/reports", { params }).then((r) => r.data),

  getStats: (period: "today" | "week" | "month") =>
    api.get<Stats>("/stats", { params: { period } }).then((r) => r.data),

  submitFormResponse: (form_id: number, data: Record<string, unknown>) =>
    api.post("/form-responses", { form_id, data }).then((r) => r.data),

  listFormResponses: (form_id?: number) =>
    api.get("/form-responses", { params: { form_id } }).then((r) => r.data),

  updateFormResponse: (id: number, data: Record<string, string>) =>
    api.patch<FormResponse>(`/form-responses/${id}`, data).then((r) => r.data),

  deleteFormResponse: (id: number) => api.delete(`/form-responses/${id}`),
};

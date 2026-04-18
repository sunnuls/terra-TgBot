import { api } from "./client";

export interface FormField {
  id: string;
  type: "date" | "number" | "text" | "select_one" | "select_many" | "table";
  label: string;
  required: boolean;
  source?: string;
  options?: string[];
  min?: number;
  max?: number;
  placeholder?: string;
  columns?: string[];
}

export interface FlowNode {
  id: string;
  type: "start" | "date" | "number" | "choice" | "text" | "confirm";
  label: string;
  options?: string[];
  source?: string; // dict source: machine_kinds, activities_tech, activities_hand, locations, locations_field, crops, machine_items
  defaultNextId?: string;
  conditionalNext?: { option: string; nextId: string }[];
  position: { x: number; y: number };
}

export interface FormFlow {
  nodes: FlowNode[];
  startId: string;
}

export interface FormTemplate {
  id: number;
  name: string;
  title: string;
  schema: { fields: FormField[]; flow?: FormFlow };
  is_active: boolean;
  created_by: number | null;
  created_at: string;
  roles: string[];
}

export const formsApi = {
  listForms: () => api.get<FormTemplate[]>("/forms").then((r) => r.data),

  getForm: (id: number) => api.get<FormTemplate>(`/forms/${id}`).then((r) => r.data),

  getFormByName: (name: string) =>
    api.get<FormTemplate[]>("/forms").then((r) => {
      const found = r.data.find((f) => f.name === name);
      if (!found) throw new Error(`Form '${name}' not found`);
      return found;
    }),
};

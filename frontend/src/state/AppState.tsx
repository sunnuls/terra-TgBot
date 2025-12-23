import React, { createContext, useContext, useMemo, useReducer } from "react";

export type Role = "admin" | "brigadier" | "it" | "tim" | "user";

export type Profile = {
  user_id: number;
  username: string;
  first_name: string;
  full_name: string;
  phone?: string;
  role: Role;
};

export type MenuAction = {
  action: string;
  title: string;
  hint?: string;
};

type State = {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  profile?: Profile;
  actions: MenuAction[];
};

type Action =
  | { type: "loading" }
  | { type: "ready"; profile: Profile; actions: MenuAction[] }
  | { type: "error"; error: string }
  | { type: "logout" };

const initialState: State = {
  status: "idle",
  actions: [],
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "loading":
      return { ...state, status: "loading", error: undefined };
    case "ready":
      return { status: "ready", profile: action.profile, actions: action.actions };
    case "error":
      return { ...state, status: "error", error: action.error };
    case "logout":
      return initialState;
    default:
      return state;
  }
}

type Ctx = {
  state: State;
  setReady: (profile: Profile, actions: MenuAction[]) => void;
  setError: (error: string) => void;
  setLoading: () => void;
};

const AppStateContext = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const value = useMemo<Ctx>(
    () => ({
      state,
      setReady: (profile: Profile, actions: MenuAction[]) => dispatch({ type: "ready", profile, actions }),
      setError: (error: string) => dispatch({ type: "error", error }),
      setLoading: () => dispatch({ type: "loading" }),
    }),
    [state]
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("AppStateContext missing");
  return ctx;
}

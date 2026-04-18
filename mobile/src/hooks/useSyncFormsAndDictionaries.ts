import { useEffect, useRef } from "react";
import { AppState, AppStateStatus } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { invalidateFormsAndDictionaries } from "../lib/syncDataCaches";

/**
 * При возврате приложения из фона обновляет формы и справочники с сервера.
 */
export function useSyncFormsAndDictionaries() {
  const qc = useQueryClient();
  const appState = useRef(AppState.currentState);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (next: AppStateStatus) => {
      if (appState.current.match(/inactive|background/) && next === "active") {
        void invalidateFormsAndDictionaries(qc);
      }
      appState.current = next;
    });
    return () => sub.remove();
  }, [qc]);
}

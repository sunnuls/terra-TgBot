import { QueryClient } from "@tanstack/react-query";

/**
 * Сбрасывает кэш форм и справочников, чтобы подтянуть актуальные данные с сервера
 * после изменений в веб-админке (конструктор форм, словари ОТД/бригад и т.д.).
 */
export function invalidateFormsAndDictionaries(qc: QueryClient): Promise<void[]> {
  return Promise.all([
    qc.invalidateQueries({ queryKey: ["forms"] }),
    qc.invalidateQueries({ queryKey: ["dictionaries"] }),
    qc.invalidateQueries({ queryKey: ["flow-form"] }),
    qc.invalidateQueries({ queryKey: ["form"] }),
    // Статистика на главной может зависеть от новых отчётов
    qc.invalidateQueries({ queryKey: ["stats"] }),
  ]);
}

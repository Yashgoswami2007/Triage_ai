import type { TriageResponse, BackendSeverity } from "./api";

type HistoryItem = {
  id: string;
  ts: number;
  language: string;
  symptomsPreview: string;
  severity: BackendSeverity;
};

const HISTORY_KEY = "triage:web:history";
const CACHE_KEY = (lang: string) => `triage:web:last:${lang}`;

function safeParse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function loadHistory(): HistoryItem[] {
  const items = safeParse<HistoryItem[]>(localStorage.getItem(HISTORY_KEY));
  return Array.isArray(items) ? items : [];
}

export function pushHistory(item: HistoryItem, maxItems = 20): HistoryItem[] {
  const current = loadHistory();
  const next = [item, ...current].slice(0, maxItems);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  return next;
}

export function loadCachedResponse(language: string): TriageResponse | null {
  return safeParse<TriageResponse>(localStorage.getItem(CACHE_KEY(language)));
}

export function saveCachedResponse(language: string, resp: TriageResponse) {
  localStorage.setItem(CACHE_KEY(language), JSON.stringify(resp));
}

export function clearForLanguage(language: string) {
  localStorage.removeItem(CACHE_KEY(language));
}


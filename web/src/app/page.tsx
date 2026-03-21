"use client";

import React, { useEffect, useMemo, useState } from "react";
import LanguageSelector, { getDefaultLanguage, normalizeLanguage } from "../components/LanguageSelector";
import SymptomInput from "../components/SymptomInput";
import TriageResult from "../components/TriageResult";
import type { BackendSeverity, TriageResponse } from "../lib/api";
import { loadCachedResponse, loadHistory, pushHistory, saveCachedResponse } from "../lib/storage";
import { triageSymptoms } from "../lib/api";
import { useTranslations } from "../lib/useTranslations";
import type { Language } from "../lib/translations";

const DEFAULT_SYMPTOMS = "";

export default function Page() {
  const [language, setLanguage] = useState<Language>("English");
  const [symptoms, setSymptoms] = useState<string>(DEFAULT_SYMPTOMS);
  const [resp, setResp] = useState<TriageResponse | null>(null);
  const [history, setHistory] = useState<
    { id: string; ts: number; language: string; symptomsPreview: string; severity: BackendSeverity }[]
  >([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [offlineMode, setOfflineMode] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const t = useTranslations(language);

  useEffect(() => {
    const initial = getDefaultLanguage();
    setLanguage(normalizeLanguage(initial) as Language);
  }, []);

  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  useEffect(() => {
    const cached = loadCachedResponse(language);
    if (cached) {
      setResp(cached);
      setOfflineMode(true);
    } else {
      setOfflineMode(false);
    }
  }, [language]);

  const symptomsPreview = useMemo(() => {
    const s = symptoms.trim();
    if (!s) return "";
    return s.length > 80 ? `${s.slice(0, 80)}...` : s;
  }, [symptoms]);

  async function onSubmit() {
    setErrorMsg("");
    setOfflineMode(false);
    const trimmed = symptoms.trim();
    if (trimmed.length < 3) {
      setErrorMsg(t.minCharsError);
      return;
    }

    setLoading(true);
    try {
      const data = await triageSymptoms({ symptoms: trimmed, language });
      setResp(data);
      saveCachedResponse(language, data);

      setHistory((prev) => {
        const item = {
          id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
          ts: Date.now(),
          language,
          symptomsPreview,
          severity: data.severity,
        };
        const next = pushHistory(item);
        return next;
      });
    } catch (e: any) {
      const cached = loadCachedResponse(language);
      if (cached) {
        setResp(cached);
        setOfflineMode(true);
        setErrorMsg(t.offlineMode);
      } else {
        setErrorMsg(e?.message || "Unable to triage right now.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <h1 style={{ margin: "6px 0 0 0" }}>{t.appTitle}</h1>
      <div className="muted" style={{ marginTop: 6, lineHeight: 1.35 }}>
        {t.subtitle}
      </div>

      <LanguageSelector value={language} onChange={(l) => setLanguage(l as Language)} t={t} />

      <SymptomInput symptoms={symptoms} setSymptoms={setSymptoms} t={t} />

      <div className="row" style={{ marginTop: 10 }}>
        <button className="primary" type="button" onClick={onSubmit} disabled={loading}>
          {loading ? t.submitLoading : t.submitButton}
        </button>
        <div className="small muted">{t.disclaimer}</div>
      </div>

      {offlineMode ? (
        <div className="panel" style={{ marginTop: 14 }}>
          <div style={{ fontWeight: 700 }}>{t.offlineMode}</div>
          <div className="muted" style={{ marginTop: 6 }}>
            {t.offlineModeDesc}
          </div>
        </div>
      ) : null}

      {errorMsg ? (
        <div className="panel" style={{ marginTop: 14, borderColor: "rgba(255,77,77,0.5)" }}>
          <div style={{ fontWeight: 700, color: "#ffb3b3" }}>{t.notice}</div>
          <div style={{ marginTop: 6 }}>{errorMsg}</div>
        </div>
      ) : null}

      {resp ? <TriageResult data={resp} t={t} /> : null}

      <div className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <div style={{ fontWeight: 800 }}>{t.historyTitle}</div>
            <div className="muted small">{t.historySubtitle}</div>
          </div>
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem("triage:web:history");
              setHistory([]);
            }}
          >
            {t.historyClear}
          </button>
        </div>

        {history.length ? (
          <div style={{ marginTop: 12 }}>
            {history.slice(0, 10).map((h) => (
              <div
                key={h.id}
                style={{
                  padding: "10px 0",
                  borderTop: "1px solid var(--border)",
                }}
              >
                <div style={{ fontWeight: 700 }}>
                  {h.severity} · {h.language}
                </div>
                <div className="muted" style={{ marginTop: 4, wordBreak: "break-word" }}>
                  {h.symptomsPreview}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="muted" style={{ marginTop: 12 }}>
            {t.historyEmpty}
          </div>
        )}
      </div>
    </div>
  );
}


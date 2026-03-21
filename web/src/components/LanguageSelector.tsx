"use client";

import React from "react";

const SUPPORTED_LANGUAGES = [
  "English",
  "Hindi",
  "Tamil",
  "Telugu",
  "Bengali",
  "Marathi",
  "Gujarati",
  "Kannada",
  "Thai",
  "Vietnamese",
  "Sinhala",
  "Nepali",
  "Tagalog",
  "Bahasa",
];

function languageFromBrowser(): string {
  const raw = (typeof navigator !== "undefined" ? navigator.language : "en") || "en";
  const base = raw.split("-")[0].toLowerCase();

  const map: Record<string, string> = {
    hi: "Hindi",
    ta: "Tamil",
    te: "Telugu",
    bn: "Bengali",
    mr: "Marathi",
    gu: "Gujarati",
    kn: "Kannada",
    th: "Thai",
    vi: "Vietnamese",
    si: "Sinhala",
    ne: "Nepali",
    tl: "Tagalog",
    fil: "Tagalog",
    id: "Bahasa",
    ms: "Bahasa",
  };

  return map[base] || "English";
}

export function normalizeLanguage(value: string | null | undefined): string {
  if (!value) return "English";
  const s = value.trim();
  if (!s) return "English";

  // If the user picks an English-like string, keep as-is.
  const candidate = s[0].toUpperCase() + s.slice(1).toLowerCase();
  if (SUPPORTED_LANGUAGES.includes(candidate)) return candidate;
  return "English";
}

export function getDefaultLanguage(): string {
  try {
    return languageFromBrowser();
  } catch {
    return "English";
  }
}

export default function LanguageSelector({
  value,
  onChange,
  t,
}: {
  value: string;
  onChange: (lang: string) => void;
  t: { languageLabel: string; languageHelp: string };
}) {
  return (
    <div className="row">
      <label htmlFor="lang">{t.languageLabel}</label>
      <select
        id="lang"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={t.languageLabel}
      >
        {SUPPORTED_LANGUAGES.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
      </select>
      <div className="small muted">{t.languageHelp}</div>
    </div>
  );
}

export const __internal = { SUPPORTED_LANGUAGES };


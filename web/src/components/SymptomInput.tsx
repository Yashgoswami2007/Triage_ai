"use client";

import React from "react";

const CHIPS = [
  "chest pain",
  "difficulty breathing",
  "severe headache",
  "high fever",
  "fainting",
  "vomiting",
  "cough",
  "sore throat",
  "rash",
  "severe abdominal pain",
  "bleeding",
  "stroke symptoms",
  "seizure",
];

export default function SymptomInput({
  symptoms,
  setSymptoms,
  t,
}: {
  symptoms: string;
  setSymptoms: (v: string) => void;
  t: { symptomsHelp: string; symptomsPlaceholder: string; symptomsHint: string };
}) {
  function toggleChip(chip: string) {
    const parts = symptoms
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);

    const has = parts.some((p) => p.toLowerCase() === chip.toLowerCase());
    const next = has ? parts.filter((p) => p.toLowerCase() !== chip.toLowerCase()) : [...parts, chip];
    setSymptoms(next.join(", "));
  }

  return (
    <div className="panel">
      <div className="muted" style={{ fontSize: 14, marginBottom: 10 }}>
        {t.symptomsHelp}
      </div>

      <div className="row" style={{ marginBottom: 10 }}>
        {CHIPS.map((c) => {
          const pressed = symptoms
            .split(",")
            .map((p) => p.trim().toLowerCase())
            .includes(c.toLowerCase());
          return (
            <button
              key={c}
              type="button"
              className="chip"
              aria-pressed={pressed}
              onClick={() => toggleChip(c)}
            >
              {c}
            </button>
          );
        })}
      </div>

      <textarea
        value={symptoms}
        onChange={(e) => setSymptoms(e.target.value)}
        placeholder={t.symptomsPlaceholder}
        aria-label={t.symptomsHelp}
        maxLength={2000}
      />
      <div className="small">{t.symptomsHint}</div>
    </div>
  );
}


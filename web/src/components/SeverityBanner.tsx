"use client";

import React from "react";

export type BackendSeverity = "URGENT" | "MODERATE" | "SELF_CARE";

function classFor(sev: BackendSeverity) {
  if (sev === "URGENT") return "urgent";
  if (sev === "MODERATE") return "moderate";
  return "selfcare";
}

function titleFor(sev: BackendSeverity) {
  if (sev === "URGENT") return "URGENT";
  if (sev === "MODERATE") return "MODERATE";
  return "SELF_CARE";
}

export default function SeverityBanner({ severity }: { severity: BackendSeverity }) {
  return (
    <div className={`badge ${classFor(severity)}`} role="status" aria-live="polite">
      <span>{titleFor(severity)}</span>
    </div>
  );
}


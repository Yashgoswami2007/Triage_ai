"use client";

import React from "react";
import SeverityBanner, { BackendSeverity } from "./SeverityBanner";

type Advice = {
  what_to_do_now: string[];
  self_care_steps: string[];
  monitor_for: string[];
  seek_care_if: string;
  disclaimer: string;
};

type TriageResponse = {
  severity: BackendSeverity;
  advice: Advice;
  reasoning?: string;
};

export default function TriageResult({
  data,
  t,
}: {
  data: TriageResponse;
  t: {
    whatToDoNow: string;
    selfCareSteps: string;
    monitorFor: string;
    seekCareIf: string;
    reasoning: string;
    actNow: string;
  };
}) {
  if (!data) return null;

  const sev = data.severity;
  const showUrgentAction = sev === "URGENT";
  return (
    <div className="panel">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <SeverityBanner severity={sev} />
      </div>

      {showUrgentAction ? (
        <div className="small">{t.actNow}</div>
      ) : null}

      <div style={{ marginTop: 10 }}>
        <div className="muted" style={{ fontSize: 14, marginBottom: 6 }}>
          {t.whatToDoNow}
        </div>
        <ul className="list">
          {data.advice.what_to_do_now.map((s, idx) => (
            <li key={idx} style={{ marginBottom: 6 }}>
              {s}
            </li>
          ))}
        </ul>
      </div>

      {sev !== "URGENT" && data.advice.self_care_steps.length ? (
        <div style={{ marginTop: 12 }}>
          <div className="muted" style={{ fontSize: 14, marginBottom: 6 }}>
            {t.selfCareSteps}
          </div>
          <ul className="list">
            {data.advice.self_care_steps.map((s, idx) => (
              <li key={idx} style={{ marginBottom: 6 }}>
                {s}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div style={{ marginTop: 12 }}>
        <div className="muted" style={{ fontSize: 14, marginBottom: 6 }}>
          {t.monitorFor}
        </div>
        <ul className="list">
          {data.advice.monitor_for.map((s, idx) => (
            <li key={idx} style={{ marginBottom: 6 }}>
              {s}
            </li>
          ))}
        </ul>
      </div>

      <div style={{ marginTop: 12 }}>
        <div className="muted" style={{ fontSize: 14, marginBottom: 6 }}>
          {t.seekCareIf}
        </div>
        <div>{data.advice.seek_care_if}</div>
      </div>

      {data.reasoning ? (
        <div style={{ marginTop: 12 }}>
          <div className="muted" style={{ fontSize: 14, marginBottom: 6 }}>
            {t.reasoning}
          </div>
          <div style={{ color: "#d7e3ff" }}>{data.reasoning}</div>
        </div>
      ) : null}

      <div className="small" style={{ marginTop: 12 }}>
        {data.advice.disclaimer}
      </div>
    </div>
  );
}


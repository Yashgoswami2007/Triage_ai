export type BackendSeverity = "URGENT" | "MODERATE" | "SELF_CARE";

export type Advice = {
  what_to_do_now: string[];
  self_care_steps: string[];
  monitor_for: string[];
  seek_care_if: string;
  disclaimer: string;
};

export type TriageResponse = {
  severity: BackendSeverity;
  advice: Advice;
  reasoning?: string;
};

const API_URL = "https://triage-ai-tan.vercel.app";

export async function triageSymptoms(params: {
  symptoms: string;
  language?: string | null;
}): Promise<TriageResponse> {
  if (!API_URL) {
    throw new Error("Missing NEXT_PUBLIC_TRIAGE_API_URL");
  }

  const res = await fetch(`${API_URL}/triage`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-request-id":
        typeof crypto !== "undefined" && (crypto as any).randomUUID
          ? (crypto as any).randomUUID()
          : String(Date.now()),
    },
    body: JSON.stringify({
      symptoms: params.symptoms,
      ...(params.language ? { language: params.language } : {}),
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text.slice(0, 200)}`);
  }

  // Backend contract is strict JSON; still guard for UI stability.
  const data = (await res.json()) as any;
  return data as TriageResponse;
}


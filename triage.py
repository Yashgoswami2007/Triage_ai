import json
import logging
import os
import re
import time
import threading
from enum import Enum
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from pydantic import BaseModel, Field, ValidationError


logger = logging.getLogger("triage_ai")


class Severity(str, Enum):
    URGENT = "URGENT"
    MODERATE = "MODERATE"
    SELF_CARE = "SELF_CARE"


class Advice(BaseModel):
    # Keep guidance short for low-bandwidth clients.
    what_to_do_now: List[str] = Field(default_factory=list, max_length=6)
    self_care_steps: List[str] = Field(default_factory=list, max_length=6)
    monitor_for: List[str] = Field(default_factory=list, max_length=6)
    seek_care_if: str = ""
    disclaimer: str = "This is not medical advice. If you think this is an emergency, seek help immediately from local emergency services or a healthcare professional."


class TriageResponse(BaseModel):
    severity: Severity
    advice: Advice
    reasoning: str = ""


class GeminiTriageService:
    """
    Calls Gemini to classify severity and generate short actionable guidance.

    The code never trusts model output blindly:
    - Enforces JSON parsing safety.
    - Validates against a strict response shape.
    - Applies emergency red-flag overrides for safety.
    """

    # Emergency red flags (only truly unambiguous, life-threatening signs).
    EMERGENCY_KEYWORDS: List[str] = [
        "cannot breathe",
        "blue lips",
        "bleeding won't stop",
        "face drooping",
        "arm weakness",
        "speech difficulty",
        "unconscious",
        "passed out",
        "seizure",
        "anaphylaxis",
        "swelling of tongue",
        "suicidal",
        "overdose",
        "poisoning",
        "sudden severe headache",
        "rigid abdomen",
    ]

    TRIAGE_PROMPT_TEMPLATE = """You are a cautious medical triage assistant for rural, low-resource settings.
You must classify how urgently someone should seek care based on their symptoms description.

Return ONLY valid JSON (no markdown, no backticks, no extra keys, no extra text).
The JSON MUST match this schema exactly:
{{
  "severity": "URGENT" | "MODERATE" | "SELF_CARE",
  "reasoning": "Brief clinical reasoning in 1-2 short sentences (<= 220 characters). Do not diagnose. Use cautious language.",
  "advice": {{
    "what_to_do_now": ["short actionable steps (max 6 items, each <= 120 chars)"],
    "self_care_steps": ["short home steps (max 6 items, each <= 120 chars)"],
    "monitor_for": ["red flags / worsening signs to watch (max 6 items, each <= 120 chars)"],
    "seek_care_if": "When to seek care (<= 160 chars).",
    "disclaimer": "A short safety disclaimer."
  }}
}}

Rules:
- Be balanced and discriminating. Differentiate between minor discomfort and life-threatening emergencies.
- Only choose "URGENT" for signs of immediate danger or severe, time-critical illness.
- If the symptoms seem manageable at home or with a routine clinic visit, choose "SELF_CARE" or "MODERATE".
- Do not provide exact diagnoses or long explanations.
- Keep output brief and usable in low-bandwidth contexts.
- Respond all text (reasoning and every advice string) in {language}. If language is not supported, respond in English.

Symptoms:
{symptoms}
"""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-flash",
        max_retries: int = 2,
        request_timeout_s: float = 12.0,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required.")

        self.api_key = api_key
        self.model_name = model_name
        self.max_retries = max_retries
        self.request_timeout_s = request_timeout_s

        genai.configure(api_key=self.api_key)

        self._model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=genai.GenerationConfig(
                # Temperature 0 for deterministic formatting.
                temperature=0,
                top_k=1,
                top_p=1,
                max_output_tokens=260,
                response_mime_type="application/json",
            ),
        )
        # `google-generativeai` client objects may not be fully thread-safe.
        # Gunicorn threads can lead to concurrent access to the shared model.
        self._lock = threading.Lock()

    @staticmethod
    def _normalize_severity(value: Any) -> Severity:
        if isinstance(value, Severity):
            return value

        if not isinstance(value, str):
            return Severity.URGENT

        v = value.strip().upper()
        # Normalize common variants.
        v = v.replace("-", "_").replace(" ", "_")

        mapping = {
            "URGENT": Severity.URGENT,
            "MODERATE": Severity.MODERATE,
            "SELF_CARE": Severity.SELF_CARE,
            "SELFCARE": Severity.SELF_CARE,
            "SELF_CARE.": Severity.SELF_CARE,
            "SELF-CARE": Severity.SELF_CARE,
        }
        return mapping.get(v, Severity.URGENT)

    @staticmethod
    def _normalize_language(value: Any) -> str:
        """
        Keep the language instruction tight to reduce prompt injection and formatting drift.
        """
        if value is None:
            return "English"
        if not isinstance(value, str):
            return "English"
        s = " ".join(value.strip().split())
        # Allow only letters, spaces, and a few common separators.
        s = re.sub(r"[^a-zA-Z\u00C0-\u017F _-]", "", s)  # lightweight unicode letter support
        if not s:
            return "English"
        s = s[:40]
        # Common canonicalization
        upper = s.strip().upper()
        mapping = {
            "HINDI": "Hindi",
            "TAGALOG": "Tagalog",
            "BAHASA": "Bahasa",
            "BAHASA INDONESIA": "Bahasa",
            "MALAY": "Bahasa",
        }
        return mapping.get(upper, s)

    @staticmethod
    def _extract_json_object(text: str) -> Optional[str]:
        """
        Extracts the first JSON object found in the text safely.
        Handles cases where Gemini wraps JSON in ```json ... ``` fences.
        """
        if not text:
            return None

        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Remove markdown fences.
            parts = cleaned.split("```")
            # Typical format: ```json\n{...}\n```
            if len(parts) >= 3:
                cleaned = parts[1]
            cleaned = cleaned.strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        candidate = cleaned[start : end + 1]

        # Basic guard: avoid returning extremely large blobs by accident.
        if len(candidate) > 20_000:
            return None

        return candidate

    @staticmethod
    def _sanitize_str_list(values: Any, max_items: int, max_len: int) -> List[str]:
        if not isinstance(values, list):
            return []

        out: List[str] = []
        for v in values[:max_items]:
            if isinstance(v, str):
                s = " ".join(v.strip().split())
                if s:
                    out.append(s[:max_len])
        return out

    @classmethod
    def _has_emergency_red_flags(cls, symptoms: str) -> List[str]:
        lowered = symptoms.lower()
        hits: List[str] = []
        for kw in cls.EMERGENCY_KEYWORDS:
            if kw in lowered:
                hits.append(kw)
            if len(hits) >= 2:
                break
        return hits

    @staticmethod
    def _template_advice(severity: Severity) -> Advice:
        if severity == Severity.URGENT:
            return Advice(
                what_to_do_now=[
                    "Call your local emergency number or go to the nearest ER immediately.",
                    "Do not drive yourself; ask someone to take you if possible.",
                    "If breathing is difficult, sit upright and loosen tight clothing.",
                    "If there is severe bleeding, apply firm pressure with a clean cloth.",
                ],
                self_care_steps=[],
                monitor_for=["Any worsening breathing, chest pain, confusion, fainting, or uncontrolled bleeding."],
                seek_care_if="Seek emergency care now; call emergency services again while waiting if symptoms worsen.",
                disclaimer=Advice().disclaimer,
            )

        if severity == Severity.MODERATE:
            return Advice(
                what_to_do_now=[
                    "Arrange a medical review within 24 hours (clinic or telehealth).",
                    "Rest and keep hydrated as tolerated.",
                ],
                self_care_steps=[
                    "Use OTC medicines only as directed on the label (avoid duplicate products).",
                    "If you have known conditions, follow your existing care plan.",
                ],
                monitor_for=[
                    "Worsening pain, persistent high fever, dehydration (very dry mouth, minimal urine), new breathing trouble, or symptoms spreading quickly."
                ],
                seek_care_if="Go to urgent care/ER if symptoms worsen, you cannot keep fluids down, you faint, or new major red flags appear.",
                disclaimer=Advice().disclaimer,
            )

        # SELF_CARE
        return Advice(
            what_to_do_now=[
                "Treat at home and monitor closely for 24-48 hours.",
                "Avoid heavy exertion; rest and hydrate.",
            ],
            self_care_steps=[
                "For fever or pain, use OTC medicines only per label if safe for you.",
                "Eat gentle foods if tolerated; follow any condition-specific home guidance you already use.",
            ],
            monitor_for=[
                "Symptoms that rapidly worsen, fever lasting >3 days, severe pain, new breathing difficulty, or any major red flags."
            ],
            seek_care_if="Get medical help if symptoms worsen, last longer than expected, or any major red flags appear.",
            disclaimer=Advice().disclaimer,
        )

    def _build_prompt(self, symptoms: str, language: str) -> str:
        return self.TRIAGE_PROMPT_TEMPLATE.format(symptoms=symptoms, language=language)

    def _call_gemini(self, symptoms: str, language: str) -> Dict[str, Any]:
        prompt = self._build_prompt(symptoms, language=language)

        # Minimal retry loop for transient issues; keep overall latency low.
        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            start = time.time()
            try:
                with self._lock:
                    response = self._model.generate_content(prompt)
                raw = getattr(response, "text", None) or ""
                elapsed = time.time() - start
                logger.info("Gemini call attempt=%s elapsed_ms=%s", attempt, int(elapsed * 1000))

                json_str = self._extract_json_object(raw)
                if not json_str:
                    last_error = "Gemini output contained no JSON object"
                    continue

                data = json.loads(json_str)
                if not isinstance(data, dict):
                    last_error = "Gemini JSON root was not an object"
                    continue

                return data
            except Exception as e:  # noqa: BLE001
                last_error = f"{type(e).__name__}: {str(e)[:200]}"
                logger.warning("Gemini call failed attempt=%s error=%s", attempt, last_error)

                # Soft backoff; avoid long sleeps.
                if attempt < self.max_retries:
                    time.sleep(0.5 * attempt)

            # Enforce a coarse timeout guard.
            if (time.time() - start) > self.request_timeout_s:
                last_error = "Gemini call exceeded request timeout guard"
                break

        raise RuntimeError(last_error or "Gemini call failed")

    def triage(self, symptoms: str, language: Optional[str] = None) -> TriageResponse:
        normalized_symptoms = " ".join((symptoms or "").strip().split())
        lang = self._normalize_language(language)
        if len(normalized_symptoms) < 3:
            # Validation should typically catch this, but keep safe anyway.
            severity = Severity.URGENT
            advice = self._template_advice(severity)
            return TriageResponse(
                severity=severity,
                advice=advice,
                reasoning="Symptoms description is too short to assess; seek medical care urgently if you are unwell.",
            )

        gemini_data: Dict[str, Any]
        try:
            gemini_data = self._call_gemini(normalized_symptoms, language=lang)
        except Exception as e:  # noqa: BLE001
            logger.exception("Gemini triage failed; returning safe fallback: %s", str(e)[:200])
            severity = Severity.URGENT
            advice = self._template_advice(severity)
            return TriageResponse(
                severity=severity,
                advice=advice,
                reasoning="Unable to classify symptoms reliably right now; for safety, seek urgent medical attention.",
            )

        # Validate and normalize Gemini output without trusting it blindly.
        try:
            severity = self._normalize_severity(gemini_data.get("severity"))
            reasoning = str(gemini_data.get("reasoning") or "").strip()
            if not reasoning:
                reasoning = "Based on symptom severity described, you may need urgent or timely medical evaluation."

            advice_raw = gemini_data.get("advice") if isinstance(gemini_data.get("advice"), dict) else {}
            what_to_do_now = self._sanitize_str_list(advice_raw.get("what_to_do_now"), max_items=6, max_len=120)
            self_care_steps = self._sanitize_str_list(advice_raw.get("self_care_steps"), max_items=6, max_len=120)
            monitor_for = self._sanitize_str_list(advice_raw.get("monitor_for"), max_items=6, max_len=120)
            seek_care_if = str(advice_raw.get("seek_care_if") or "").strip()
            disclaimer = str(advice_raw.get("disclaimer") or "").strip()

            # If the model returns an incomplete advice object, fill from templates.
            template_advice = self._template_advice(severity)
            if not what_to_do_now:
                what_to_do_now = template_advice.what_to_do_now
            if not monitor_for:
                monitor_for = template_advice.monitor_for
            if not seek_care_if:
                seek_care_if = template_advice.seek_care_if
            if not disclaimer:
                disclaimer = template_advice.disclaimer

            # For URGENT, self_care_steps should be empty or minimal.
            if severity == Severity.URGENT:
                self_care_steps = []
            else:
                if not self_care_steps:
                    self_care_steps = template_advice.self_care_steps

            # Final schema validation (pydantic) for safety.
            advice = Advice(
                what_to_do_now=what_to_do_now,
                self_care_steps=self_care_steps,
                monitor_for=monitor_for,
                seek_care_if=seek_care_if,
                disclaimer=disclaimer,
            )

            response = TriageResponse(
                severity=severity,
                advice=advice,
                reasoning=reasoning[:240],
            )
        except (ValidationError, Exception) as e:  # noqa: BLE001
            logger.exception("Gemini output validation failed; returning safe template. error=%s", str(e)[:200])
            severity = Severity.URGENT
            advice = self._template_advice(severity)
            response = TriageResponse(
                severity=severity,
                advice=advice,
                reasoning="Unable to parse the model's triage response reliably; for safety, seek urgent medical attention.",
            )

        # Safety override: emergency red flags always force URGENT.
        hits = self._has_emergency_red_flags(normalized_symptoms)
        if hits:
            logger.info("Emergency keyword override applied: hits=%s", hits)
            severity = Severity.URGENT
            advice = self._template_advice(severity)
            hit_phrase = hits[0]
            response = TriageResponse(
                severity=severity,
                advice=advice,
                reasoning=f"Your description includes emergency red flags (e.g., {hit_phrase}); seek emergency care now.",
            )

        return response


def get_service() -> GeminiTriageService:
    """
    Creates the Gemini triage service using environment variables.

    Expected env var:
    - GEMINI_API_KEY (preferred)
    - GOOGLE_API_KEY (fallback)
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    model_name = os.environ.get("GEMINI_MODEL_NAME") or "gemini-1.5-flash"
    return GeminiTriageService(api_key=api_key, model_name=model_name)


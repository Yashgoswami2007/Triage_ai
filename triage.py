import json
import logging
import os
import re
import time
import threading
from enum import Enum
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("triage_ai")

class Severity(str, Enum):
    URGENT = "URGENT"
    MODERATE = "MODERATE"
    SELF_CARE = "SELF_CARE"

class Advice(BaseModel):
    what_to_do_now: List[str] = Field(default_factory=list, max_length=6)
    self_care_steps: List[str] = Field(default_factory=list, max_length=6)
    monitor_for: List[str] = Field(default_factory=list, max_length=6)
    seek_care_if: str = ""
    disclaimer: str = "This is not medical advice. If you think this is an emergency, seek help immediately from local emergency services or a healthcare professional."

class TriageResponse(BaseModel):
    severity: Severity
    advice: Advice
    reasoning: str = ""

class OpenRouterTriageService:
    """
    Calls OpenRouter (DeepSeek) to classify severity and generate short actionable guidance.
    """

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
        model_name: str = "deepseek/deepseek-chat:free",
        max_retries: int = 2,
        request_timeout_s: float = 20.0,
    ) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key is required.")

        self.api_key = api_key
        self.model_name = model_name
        self.max_retries = max_retries
        self.request_timeout_s = request_timeout_s

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        self._lock = threading.Lock()

    @staticmethod
    def _normalize_severity(value: Any) -> Severity:
        if isinstance(value, Severity):
            return value
        if not isinstance(value, str):
            return Severity.URGENT
        v = value.strip().upper().replace("-", "_").replace(" ", "_")
        mapping = {
            "URGENT": Severity.URGENT,
            "MODERATE": Severity.MODERATE,
            "SELF_CARE": Severity.SELF_CARE,
            "SELFCARE": Severity.SELF_CARE,
        }
        return mapping.get(v, Severity.URGENT)

    @staticmethod
    def _normalize_language(value: Any) -> str:
        if not isinstance(value, str):
            return "English"
        s = re.sub(r"[^a-zA-Z\u00C0-\u017F _-]", "", value.strip())[:40]
        return s or "English"

    @staticmethod
    def _extract_json_object(text: str) -> Optional[str]:
        if not text: return None
        cleaned = text.strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            for p in parts:
                if "{" in p and "}" in p:
                    cleaned = p.strip()
                    if cleaned.lower().startswith("json"):
                        cleaned = cleaned[4:].strip()
                    break
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start: return None
        return cleaned[start : end + 1]

    @staticmethod
    def _sanitize_str_list(values: Any, max_items: int, max_len: int) -> List[str]:
        if not isinstance(values, list): return []
        return [" ".join(str(v).strip().split())[:max_len] for v in values[:max_items] if v]

    @classmethod
    def _has_emergency_red_flags(cls, symptoms: str) -> List[str]:
        lowered = symptoms.lower()
        return [kw for kw in cls.EMERGENCY_KEYWORDS if kw in lowered][:2]

    @staticmethod
    def _template_advice(severity: Severity) -> Advice:
        if severity == Severity.URGENT:
            return Advice(
                what_to_do_now=["Call emergency services or go to the ER now.", "Do not drive yourself."],
                monitor_for=["Worsening breathing, chest pain, or fainting."],
                seek_care_if="Symptoms worsen while waiting.",
            )
        if severity == Severity.MODERATE:
            return Advice(
                what_to_do_now=["See a doctor within 24 hours.", "Rest and hydrate."],
                self_care_steps=["Monitor symptoms and follow existing care plans."],
                monitor_for=["New red flags or symptoms spreading quickly."],
                seek_care_if="You cannot keep fluids down or feel much worse.",
            )
        return Advice(
            what_to_do_now=["Rest at home and monitor for 48 hours."],
            self_care_steps=["Gentle recovery at home."],
            monitor_for=["High fever lasting >3 days or new severe pain."],
            seek_care_if="Symptoms worsen significantly.",
        )

    def _call_openrouter(self, symptoms: str, language: str) -> Dict[str, Any]:
        prompt = self.TRIAGE_PROMPT_TEMPLATE.format(symptoms=symptoms, language=language)
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    timeout=self.request_timeout_s
                )
                raw = response.choices[0].message.content or ""
                json_str = self._extract_json_object(raw)
                if not json_str: raise ValueError("No JSON in response")
                return json.loads(json_str)
            except Exception as e:
                last_error = str(e)
                logger.warning("OpenRouter failed attempt %d: %s", attempt, last_error)
                time.sleep(1)
        raise RuntimeError(f"OpenRouter call failed: {last_error}")

    def triage(self, symptoms: str, language: Optional[str] = None) -> TriageResponse:
        normalized_symptoms = " ".join((symptoms or "").strip().split())
        lang = self._normalize_language(language)
        
        if len(normalized_symptoms) < 3:
            severity = Severity.URGENT
            return TriageResponse(severity=severity, advice=self._template_advice(severity), reasoning="Too short to assess.")

        try:
            data = self._call_openrouter(normalized_symptoms, language=lang)
            severity = self._normalize_severity(data.get("severity"))
            reasoning = str(data.get("reasoning") or "").strip()[:240]
            adv_raw = data.get("advice") if isinstance(data.get("advice"), dict) else {}
            
            advice = Advice(
                what_to_do_now=self._sanitize_str_list(adv_raw.get("what_to_do_now"), 6, 120) or self._template_advice(severity).what_to_do_now,
                self_care_steps=self._sanitize_str_list(adv_raw.get("self_care_steps"), 6, 120) or self._template_advice(severity).self_care_steps,
                monitor_for=self._sanitize_str_list(adv_raw.get("monitor_for"), 6, 120) or self._template_advice(severity).monitor_for,
                seek_care_if=str(adv_raw.get("seek_care_if") or "").strip()[:160] or self._template_advice(severity).seek_care_if,
                disclaimer=str(adv_raw.get("disclaimer") or "").strip() or Advice().disclaimer
            )
            response = TriageResponse(severity=severity, advice=advice, reasoning=reasoning)
        except Exception as e:
            logger.exception("Triage failed: %s", e)
            severity = Severity.URGENT
            response = TriageResponse(severity=severity, advice=self._template_advice(severity), reasoning="Service error; seek care safely.")

        hits = self._has_emergency_red_flags(normalized_symptoms)
        if hits:
            severity = Severity.URGENT
            response = TriageResponse(severity=severity, advice=self._template_advice(severity), reasoning=f"Emergency red flag detected: {hits[0]}")

        return response

def get_service() -> OpenRouterTriageService:
    api_key = os.environ.get("OPENROUTER_API_KEY") or ""
    model_name = os.environ.get("OPENROUTER_MODEL") or "deepseek/deepseek-chat:free"
    return OpenRouterTriageService(api_key=api_key, model_name=model_name)

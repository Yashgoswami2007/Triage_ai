"use client";

import { useMemo } from "react";
import { getTranslation, type Language } from "./translations";

export function useTranslations(language: Language) {
  return useMemo(() => getTranslation(language), [language]);
}

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import (
    EMAIL_NOISE_PATTERNS,
    FAMILY_KEYWORDS,
    INCIDENT_FAMILY_BY_TYPE,
    TYPE_KEYWORDS,
)

try:
    import spacy  # type: ignore
except Exception:  # pragma: no cover
    spacy = None


BLOCK_RE = re.compile(
    r"\b(\d{1,4}(?:\s*-\s*\d{1,4})?\s+block\s+of\s+[A-Za-z0-9 .&'-]+?(?:NW|NE|SW|SE))\b",
    flags=re.IGNORECASE,
)
INTERSECTION_RE = re.compile(
    r"\b([A-Za-z0-9 .&'-]+?)\s*(?:and|&)\s*([A-Za-z0-9 .&'-]+?(?:NW|NE|SW|SE))\b",
    flags=re.IGNORECASE,
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_text_for_matching(text: str) -> str:
    text = normalize_whitespace(text)
    text = re.sub(r"\bN\.?W\.?\b", "NW", text, flags=re.IGNORECASE)
    text = re.sub(r"\bN\.?E\.?\b", "NE", text, flags=re.IGNORECASE)
    text = re.sub(r"\bS\.?W\.?\b", "SW", text, flags=re.IGNORECASE)
    text = re.sub(r"\bS\.?E\.?\b", "SE", text, flags=re.IGNORECASE)
    return text


def deduplicate_repeated_message(text: str) -> str:
    text = normalize_whitespace(text)
    half = len(text) // 2
    if half > 50:
        first = text[:half].strip()
        second = text[half:].strip()
        if first and second and first[:120].lower() == second[:120].lower():
            return first
    return text


def clean_email_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = deduplicate_repeated_message(text)
    text = normalize_text_for_matching(text)
    text = re.sub(r"This is a message from.*?(?=[A-Z])", "", text, flags=re.IGNORECASE)
    for pattern in EMAIL_NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return normalize_whitespace(text)


class IncidentClassifier:
    def __init__(self, model_path: Path | str = "spacy_model") -> None:
        self.model_path = Path(model_path)
        self.nlp = self._load_model(self.model_path)

    def _load_model(self, model_path: Path):
        if spacy is None or not model_path.exists():
            return None
        try:
            return spacy.load(model_path)
        except Exception:
            return None

    def _keyword_scores(self, text: str, keyword_map: Dict[str, list[str]]) -> Dict[str, int]:
        lowered = text.lower()
        scores = {label: 0 for label in keyword_map}
        for label, keywords in keyword_map.items():
            for kw in keywords:
                if kw in lowered:
                    scores[label] += 1
        return scores

    def predict_incident_type(self, text: str) -> Tuple[str, float, str]:
        cleaned = clean_email_text(text)
        if not cleaned:
            return "Other", 0.0, "empty"

        if self.nlp is not None and "textcat" in self.nlp.pipe_names:
            try:
                doc = self.nlp(cleaned)
                if doc.cats:
                    label, score = max(doc.cats.items(), key=lambda item: item[1])
                    if score >= 0.55:
                        return label, float(score), "spacy"
            except Exception:
                pass

        scores = self._keyword_scores(cleaned, TYPE_KEYWORDS)
        label = max(scores, key=scores.get)
        if scores[label] > 0:
            confidence = min(0.9, 0.45 + 0.15 * scores[label])
            return label, float(confidence), "keywords"

        family, family_score, source = self.predict_incident_family(cleaned)
        if family != "Other":
            return family, family_score, source
        return "Other", 0.0, "fallback"

    def predict_incident_family(self, text: str) -> Tuple[str, float, str]:
        incident_type, score, source = self.predict_incident_type_from_keywords_or_model(text)
        family = INCIDENT_FAMILY_BY_TYPE.get(incident_type, incident_type)
        if family in FAMILY_KEYWORDS or family == "Other":
            return family, score, source
        return "Other", 0.0, source

    def predict_incident_type_from_keywords_or_model(self, text: str) -> Tuple[str, float, str]:
        cleaned = clean_email_text(text)
        if not cleaned:
            return "Other", 0.0, "empty"

        if self.nlp is not None and "textcat" in self.nlp.pipe_names:
            try:
                doc = self.nlp(cleaned)
                if doc.cats:
                    label, score = max(doc.cats.items(), key=lambda item: item[1])
                    if score >= 0.55:
                        return label, float(score), "spacy"
            except Exception:
                pass

        type_scores = self._keyword_scores(cleaned, TYPE_KEYWORDS)
        type_label = max(type_scores, key=type_scores.get)
        if type_scores[type_label] > 0:
            return type_label, min(0.9, 0.45 + 0.15 * type_scores[type_label]), "keywords"

        family_scores = self._keyword_scores(cleaned, FAMILY_KEYWORDS)
        family_label = max(family_scores, key=family_scores.get)
        if family_scores[family_label] > 0:
            return family_label, min(0.85, 0.4 + 0.12 * family_scores[family_label]), "keywords"

        return "Other", 0.0, "fallback"

    def extract_spacy_location_candidate(self, text: str) -> Optional[str]:
        if self.nlp is None:
            return None
        try:
            doc = self.nlp(text)
        except Exception:
            return None
        candidates = [ent.text.strip(" .,;:") for ent in doc.ents if ent.label_ in {"FAC", "GPE", "LOC", "ORG"}]
        candidates = [c for c in candidates if len(c) > 2]
        if not candidates:
            return None
        candidates.sort(key=len, reverse=True)
        return candidates[0]


DEFAULT_CLASSIFIER = IncidentClassifier()

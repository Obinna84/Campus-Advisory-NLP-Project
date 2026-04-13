from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from .config import INCIDENT_FAMILY_BY_TYPE
from .geo import extract_location, resolve_location
from .nlp import DEFAULT_CLASSIFIER, clean_email_text


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_alerts.csv"


def load_default_data() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH, encoding="latin-1")



def derive_family(category: str) -> str:
    if not isinstance(category, str) or not category.strip():
        return "Other"
    return INCIDENT_FAMILY_BY_TYPE.get(category.strip(), category.strip())



def classify_record(description: str, existing_category: Optional[str] = None) -> tuple[str, str, float, str]:
    if isinstance(existing_category, str) and existing_category.strip():
        incident_type = existing_category.strip()
        family = derive_family(incident_type)
        return incident_type, family, 1.0, "provided"

    incident_type, confidence, source = DEFAULT_CLASSIFIER.predict_incident_type_from_keywords_or_model(description)
    family = derive_family(incident_type)
    return incident_type, family, confidence, source



def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    if "description" not in work.columns:
        work["description"] = ""
    work["description"] = work["description"].fillna("").map(clean_email_text)

    if "category" not in work.columns:
        work["category"] = ""
    work["category"] = work["category"].fillna("")

    incident_types = []
    families = []
    confidences = []
    sources = []
    locations = []
    lats = []
    lons = []
    geocode_sources = []

    for _, row in work.iterrows():
        description = row.get("description", "")
        incident_type, family, confidence, source = classify_record(description, row.get("category"))
        spacy_loc = DEFAULT_CLASSIFIER.extract_spacy_location_candidate(description)
        location = row.get("location", "") if isinstance(row.get("location", ""), str) else ""
        if not location.strip():
            location = extract_location(description, spacy_candidate=spacy_loc)

        location_result = resolve_location(location, raw_text=description)
        final_location = location_result.get("name") or location
        lat = location_result.get("lat")
        lon = location_result.get("lon")

        incident_types.append(incident_type)
        families.append(family)
        confidences.append(round(float(confidence), 3))
        sources.append(source)
        locations.append(final_location)
        lats.append(lat)
        lons.append(lon)
        geocode_sources.append(location_result.get("source"))

    work["incident_type"] = incident_types
    work["category"] = incident_types
    work["incident_family"] = families
    work["model_confidence"] = confidences
    work["classification_source"] = sources
    work["location"] = locations
    work["date"] = pd.to_datetime(work.get("date", pd.NaT), errors="coerce", format="mixed")
    work["lat"] = lats
    work["lon"] = lons
    work["geocode_source"] = geocode_sources

    return work

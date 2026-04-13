from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from geopy.geocoders import Nominatim

from .config import DEFAULT_CITY
from .coordinates import (
    append_unresolved_location,
    get_best_manual_match,
    get_exact_manual_entry,
    manual_entry_has_coordinates,
    normalize_location_text,
    within_campus_bounds,
)
from .nlp import BLOCK_RE, INTERSECTION_RE, normalize_text_for_matching

REMOTE_GEOCODING_ENABLED = os.getenv("ALLOW_REMOTE_GEOCODING", "0") == "1"

LOCATION_PREFIXES = [
    "outside of ",
    "outside ",
    "inside ",
    "near the ",
    "near ",
    "at the ",
    "at ",
    "by the ",
    "by ",
    "behind the ",
    "behind ",
    "in front of the ",
    "in front of ",
    "across from the ",
    "across from ",
    "next to the ",
    "next to ",
]


def _strip_location_prefixes(text: str) -> str:
    cleaned = text.strip()
    lowered = cleaned.lower()
    for prefix in LOCATION_PREFIXES:
        if lowered.startswith(prefix):
            return cleaned[len(prefix) :].strip(" .,;:")
    return cleaned.strip(" .,;:")


LOCATION_CHUNK_PATTERNS = [
    r"\b(?:near|at|in|on|outside|inside|behind|by|around|across from|next to)\s+(?:the\s+)?([A-Z][A-Za-z0-9 .&'/-]+?)(?=\s+at\s+\d|[\.,;]|$)",
    r"\b(rear of the [A-Z][A-Za-z0-9 .&'/-]+?)(?=\s+located|\s+in\s+the|[\.,;]|$)",
]


def canonicalize_location(candidate: str) -> str:
    if not candidate:
        return ""
    cleaned = _strip_location_prefixes(candidate)
    manual = get_exact_manual_entry(cleaned) or get_best_manual_match(cleaned)
    if manual:
        return manual["name"]
    return cleaned.strip(" .,;:")



def extract_location(text: str, spacy_candidate: Optional[str] = None) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""

    cleaned = normalize_text_for_matching(text)

    alias_match = get_best_manual_match(cleaned)
    if alias_match:
        return alias_match["name"]

    block_match = BLOCK_RE.search(cleaned)
    if block_match:
        return canonicalize_location(block_match.group(1))

    intersection_match = INTERSECTION_RE.search(cleaned)
    if intersection_match:
        first = intersection_match.group(1).strip(" .,;:")
        second = intersection_match.group(2).strip(" .,;:")
        if len(first) > 1 and len(second) > 1:
            return canonicalize_location(f"{first} & {second}")

    for pattern in LOCATION_CHUNK_PATTERNS:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            location = _strip_location_prefixes(match.group(1))
            if len(location) > 2:
                return canonicalize_location(location)

    if spacy_candidate:
        return canonicalize_location(spacy_candidate)

    return ""


@lru_cache(maxsize=1)
def get_geocoder() -> Nominatim:
    return Nominatim(user_agent="campus_advisory_nlp_project")



def _candidate_queries(location: str) -> List[str]:
    base = _strip_location_prefixes(location)
    normalized = normalize_location_text(base)
    if not normalized:
        return []

    variants = [base]
    manual = get_best_manual_match(base)
    if manual:
        variants.append(manual["name"])

    queries = []
    for variant in variants:
        queries.extend(
            [
                variant,
                f"{variant}, Howard University",
                f"{variant}, Howard University, {DEFAULT_CITY}",
                f"{variant}, {DEFAULT_CITY}",
            ]
        )

    seen = set()
    ordered = []
    for q in queries:
        key = normalize_location_text(q)
        if key and key not in seen:
            ordered.append(q)
            seen.add(key)
    return ordered


@lru_cache(maxsize=1024)
def geocode_location(location: str) -> Tuple[Optional[float], Optional[float]]:
    result = resolve_location(location)
    return result.get("lat"), result.get("lon")



def resolve_location(location: str, raw_text: str = "") -> Dict[str, Optional[object]]:
    if not isinstance(location, str) or not location.strip():
        return {"name": None, "lat": None, "lon": None, "source": "empty", "query": None}

    cleaned = canonicalize_location(location)

    manual_exact = get_exact_manual_entry(cleaned)
    if manual_entry_has_coordinates(manual_exact):
        return {
            "name": manual_exact["name"],
            "lat": float(manual_exact["lat"]),
            "lon": float(manual_exact["lon"]),
            "source": "manual_exact",
            "query": manual_exact["name"],
        }

    manual_match = get_best_manual_match(cleaned)
    if manual_entry_has_coordinates(manual_match):
        return {
            "name": manual_match["name"],
            "lat": float(manual_match["lat"]),
            "lon": float(manual_match["lon"]),
            "source": "manual_alias",
            "query": manual_match["name"],
        }

    if not REMOTE_GEOCODING_ENABLED:
        if raw_text or cleaned:
            append_unresolved_location(raw_text or cleaned, cleaned, "remote_geocoding_disabled_or_missing_manual_coordinate")
        return {"name": cleaned, "lat": None, "lon": None, "source": "manual_missing", "query": cleaned}

    geocoder = get_geocoder()
    for query in _candidate_queries(cleaned):
        try:
            result = geocoder.geocode(query, exactly_one=True, country_codes="us")
        except Exception:
            result = None
        if result is None:
            continue

        lat = float(result.latitude)
        lon = float(result.longitude)
        if not within_campus_bounds(lat, lon):
            continue

        return {
            "name": cleaned,
            "lat": lat,
            "lon": lon,
            "source": "remote_geocoder",
            "query": query,
        }

    append_unresolved_location(raw_text or cleaned, cleaned, "no_geocoder_result_in_bounds")
    return {"name": cleaned, "lat": None, "lon": None, "source": "unresolved", "query": cleaned}

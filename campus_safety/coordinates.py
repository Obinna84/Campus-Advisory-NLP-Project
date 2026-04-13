from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REGISTRY_PATH = DATA_DIR / "manual_coordinate_registry.csv"
UNRESOLVED_LOG_PATH = DATA_DIR / "unresolved_locations.csv"

CAMPUS_BOUNDS = {
    "min_lat": 38.9150,
    "max_lat": 38.9268,
    "min_lon": -77.0265,
    "max_lon": -77.0140,
}


def normalize_location_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"\bn\.?w\.?\b", "nw", text)
    text = re.sub(r"\bn\.?e\.?\b", "ne", text)
    text = re.sub(r"\bs\.?w\.?\b", "sw", text)
    text = re.sub(r"\bs\.?e\.?\b", "se", text)
    text = re.sub(r"\bctr\b", "center", text)
    text = re.sub(r"\bbldg\b", "building", text)
    text = re.sub(r"\bave\b", "avenue", text)
    text = re.sub(r"\bav\b", "avenue", text)
    text = re.sub(r"\bst\b", "street", text)
    text = re.sub(r"\bpl\b", "place", text)
    text = re.sub(r"\bblk\b", "block", text)
    text = re.sub(r"\bnw\s*$", " northwest", text)
    text = re.sub(r"\bne\s*$", " northeast", text)
    text = re.sub(r"\bsw\s*$", " southwest", text)
    text = re.sub(r"\bse\s*$", " southeast", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,:;-")
    return text


def _safe_float(value: str) -> Optional[float]:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def load_coordinate_registry() -> Dict[str, Dict[str, Any]]:
    registry: Dict[str, Dict[str, Any]] = {}
    if not REGISTRY_PATH.exists():
        return registry

    with REGISTRY_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = str(row.get("key", "")).strip()
            if not key:
                continue
            aliases = [a.strip() for a in str(row.get("aliases", "")).split("|") if a.strip()]
            name = str(row.get("name", key)).strip()
            lat = _safe_float(row.get("lat", ""))
            lon = _safe_float(row.get("lon", ""))
            normalized_aliases = sorted(
                {normalize_location_text(name), *(normalize_location_text(alias) for alias in aliases if alias)},
                key=len,
                reverse=True,
            )
            registry[key] = {
                "key": key,
                "name": name,
                "category": str(row.get("category", "")).strip(),
                "lat": lat,
                "lon": lon,
                "notes": str(row.get("notes", "")).strip(),
                "aliases": aliases,
                "normalized_aliases": [a for a in normalized_aliases if a],
            }
    return registry


@lru_cache(maxsize=1)
def build_alias_index() -> Dict[str, Dict[str, Any]]:
    alias_index: Dict[str, Dict[str, Any]] = {}
    for entry in load_coordinate_registry().values():
        for alias in entry["normalized_aliases"]:
            alias_index[alias] = entry
    return alias_index


def get_best_manual_match(text: str) -> Optional[Dict[str, Any]]:
    normalized = normalize_location_text(text)
    if not normalized:
        return None

    matches: List[tuple[int, Dict[str, Any]]] = []
    for alias, entry in build_alias_index().items():
        if alias and alias in normalized:
            matches.append((len(alias), entry))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def get_exact_manual_entry(text: str) -> Optional[Dict[str, Any]]:
    normalized = normalize_location_text(text)
    if not normalized:
        return None
    for entry in load_coordinate_registry().values():
        if normalized in entry["normalized_aliases"]:
            return entry
    return None


def within_campus_bounds(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    return (
        CAMPUS_BOUNDS["min_lat"] <= float(lat) <= CAMPUS_BOUNDS["max_lat"]
        and CAMPUS_BOUNDS["min_lon"] <= float(lon) <= CAMPUS_BOUNDS["max_lon"]
    )


def manual_entry_has_coordinates(entry: Optional[Dict[str, Any]]) -> bool:
    return bool(entry and entry.get("lat") is not None and entry.get("lon") is not None)


def append_unresolved_location(raw_text: str, extracted_text: str, note: str = "") -> None:
    UNRESOLVED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_file = not UNRESOLVED_LOG_PATH.exists()
    with UNRESOLVED_LOG_PATH.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(["raw_text", "extracted_text", "note"])
        writer.writerow([raw_text, extracted_text, note])


def list_missing_coordinates() -> List[Dict[str, Any]]:
    missing = []
    for entry in load_coordinate_registry().values():
        if entry.get("lat") is None or entry.get("lon") is None:
            missing.append(entry)
    return missing

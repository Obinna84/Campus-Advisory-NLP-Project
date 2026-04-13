# Campus Advisory NLP Project

An upgraded Streamlit project for classifying campus safety reports, extracting locations, and visualizing incidents on an interactive map.

## What this version fixes

This upgrade focuses on the issues that usually keep class projects from feeling production-ready:

- removes duplicated location keys and inconsistent coordinate mappings
- splits the logic into reusable modules instead of keeping everything in one large file
- keeps spaCy connected, but adds a safe keyword fallback so the app still works when the model is unavailable
- improves location extraction with campus aliases, block matching, intersection detection, and cached geocoding
- adds incident family grouping, confidence scores, search, better filtering, and cleaner summaries
- makes the README and project structure submission-ready

## Features

- **Incident classification** using a hybrid workflow:
  - spaCy `textcat` predictions when a compatible model is available
  - keyword fallback when the model is missing or low-confidence
- **Location extraction** from free-form reports
- **Geocoding with caching** for faster repeat lookups
- **Interactive Folium map** with clustered markers
- **Filterable dashboard** for incident families, incident types, dates, and text search
- **Single-report parser** so you can paste in a new incident and preview how it is classified

## Project structure

```text
Campus-Advisory-NLP-Project-main/
├── app.py
├── classifications.py
├── campus_safety/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── geo.py
│   ├── nlp.py
│   └── visuals.py
├── data/
│   └── sample_alerts.csv
├── documentation/
│   └── spacy_classifications.txt
├── requirements.txt
└── spacy_model/
```

## Setup

Create and activate a virtual environment first if you want a clean local install.

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Optional: enable live geocoding for locations that are not already in the project lookup table.

```bash
# macOS / Linux
export ALLOW_REMOTE_GEOCODING=1

# Windows PowerShell
$env:ALLOW_REMOTE_GEOCODING = "1"
```

## Run the app

```bash
streamlit run app.py
```

## Evaluate the classifier flow

```bash
python classifications.py
```

This evaluation script checks the enriched sample dataset, prints a simple type-accuracy view against the provided labels, and shows a few demo predictions.

## Expected CSV format

Required column:

- `description`

Optional columns:

- `location`
- `date`
- `category`

If `location` or `category` is missing, the app will try to infer them.

## Architecture notes

### 1. Classification strategy

The app predicts an **incident type** first and then derives a broader **incident family**.

Examples:

- `Armed Robbery` → `Violence`
- `Motor Theft` → `Vehicle Incident`
- `Fire` → `Safety Hazard`

This makes the dashboard easier to analyze while preserving detailed labels.

### 2. Location strategy

The pipeline checks locations in this order:

1. campus alias match, such as `towers`, `the yard`, or `blackburn`
2. street block extraction
3. intersection extraction
4. phrase-based fallback like `near`, `at`, `in`, or `on`
5. spaCy entity candidate fallback
6. geocoder lookup if coordinates are not already known

### 3. Why keep spaCy connected

The project keeps the spaCy model path and inference hook in place because that is still the best long-term direction for improving classification. The keyword fallback is there to make the app reliable instead of brittle.

## Best talking points for demos or interviews

You can describe the project like this:

> Built a campus safety NLP dashboard that classifies incident reports, extracts locations from free text, and maps incidents for rapid situational awareness using Streamlit, spaCy, geocoding, and Folium.

## Suggested next upgrades

- retrain the spaCy model on a larger labeled dataset
- add severity scoring and temporal trend lines
- save user-submitted incidents to a database instead of session-only memory
- deploy with Streamlit Community Cloud or another lightweight hosting service
- add automated tests for classification and location parsing


## Manual coordinates workflow

This version includes a manual coordinate registry at `data/manual_coordinate_registry.csv`.

- Paste exact Google Maps coordinates into the `lat` and `lon` columns.
- The app checks this registry before it tries any remote geocoding.
- This is the recommended workflow for Howard-specific buildings, blocks, intersections, and nicknames.
- Unresolved locations are logged to `data/unresolved_locations.csv`.

### Coordinate file columns
- `key`: stable internal id
- `name`: display name used in the app
- `category`: `howard_building` or `sample_data_location`
- `lat`, `lon`: exact coordinates you paste from Google Maps
- `aliases`: pipe-separated aliases like `Founders Library|Founders|library`
- `notes`: reminder for what point to click

### Geocoder behavior
The geocoder is now a last resort. It only runs after:
1. exact manual match
2. alias match from the registry
3. cleaned location extraction

If remote geocoding is disabled, unresolved items stay in the registry/logging workflow so you can fill them manually.

import re
from functools import lru_cache
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from streamlit.components.v1 import html

st.set_page_config(page_title="Campus Safety Language Map", layout="wide")

CAMPUS_CENTER = [38.9227, -77.0194]
DEFAULT_CITY = "Washington, DC"

CATEGORY_KEYWORDS = {
    "Sexual Misconduct": [
        "sexual abuse",
        "sexual assault",
        "inappropriately",
        "fondled",
        "groped",
        "unwanted touching",
        "touched the victim",
        "touch the victim",
    ],
    "Theft": [
        "theft",
        "stolen",
        "steal",
        "robbery",
        "burglary",
        "break-in",
        "larceny",
        "shoplifting",
        "pickpocket",
        "robbed",
        "stole",
    ],
    "Violence": [
        "assault",
        "fight",
        "battery",
        "attack",
        "shots",
        "shooting",
        "gun",
        "weapon",
        "stab",
        "injured",
        "hospital",
        "gunfire",
        "shot",
    ],
    "Suspicious Activity": [
        "suspicious",
        "unknown person",
        "lurking",
        "loitering",
        "unauthorized",
        "trespass",
    ],
    "Safety Hazard": [
        "fire",
        "smoke",
        "hazard",
        "broken light",
        "unsafe",
        "gas leak",
        "flood",
        "alarm",
        "dumpster fire",
    ],
    "Vehicle Incident": [
        "carjacking",
        "vehicle",
        "auto theft",
        "car",
        "parking",
        "collision",
        "hit and run",
    ],
}

KNOWN_LOCATIONS = {
    "towers": "Howard Plaza Towers, Howard University, Washington, DC",
    "howard plaza towers": "Howard Plaza Towers, Howard University, Washington, DC",
    "yard": "The Yard, Howard University, Washington, DC",
    "the yard": "The Yard, Howard University, Washington, DC",
    "blackburn": "Blackburn University Center, Howard University, Washington, DC",
    "founders": "Founders Library, Howard University, Washington, DC",
    "towers": "Howard Plaza Towers, Howard University, Washington, DC",
    "howard plaza towers": "Howard Plaza Towers, Howard University, Washington, DC",
    "founders library": "Founders Library, Howard University, Washington, DC",
    "blackburn center": "Blackburn University Center, Howard University, Washington, DC",
    "the yard": "The Yard, Howard University, Washington, DC",
    "douglass hall": "Douglass Hall, Howard University, Washington, DC",
    "c.h. best hall": "C.H. Best Hall, Howard University, Washington, DC",
    "chemistry building": "Chemistry Building, Howard University, Washington, DC",
    "georgia ave nw": "Georgia Ave NW, Washington, DC",
    "georgia ave": "Georgia Ave NW, Washington, DC",
    "sixth street nw": "6th St NW, Washington, DC",
    "6th street nw": "6th St NW, Washington, DC",
    "500 block of w street nw": "500 block of W Street NW, Washington, DC",
    "500 block w street nw": "500 block of W Street NW, Washington, DC",
    "200 block of v street nw": "200 block of V Street NW, Washington, DC",
    "200 block of v street n.w": "200 block of V Street NW, Washington, DC",
    "500 block of college street nw": "500 block of College Street NW, Washington, DC",
    "2500 block of georgia ave": "2500 block of Georgia Ave NW, Washington, DC",
    "2500 block of georgia ave nw": "2500 block of Georgia Ave NW, Washington, DC",
    "600 block of howard place nw": "600 block of Howard Place NW, Washington, DC",
}

KNOWN_COORDINATES = {
    "towers east": (38.920261692426386, -77.02476141279952),
    "howard plaza towers": (38.92355, -77.01942),
    "yard": (38.92319, -77.01988),
    "the yard": (38.92319, -77.01988),
    "blackburn": (38.92206, -77.02115),
    "founders": (38.92228, -77.01974),
    "towers": (38.920545498696534, -77.02404258076335),
    "howard plaza towers": (38.920545498696534, -77.02404258076335),
    "founders library": (38.92228, -77.01974),
    "blackburn center": (38.92206, -77.02115),
    "the yard": (38.92319, -77.01988),
    "douglass hall": (38.92163, -77.01935),
    "c.h. best hall": (38.92256, -77.02082),
    "chemistry building": (38.92190, -77.02105),
    "georgia ave nw": (38.92290, -77.02170),
    "georgia ave": (38.92290, -77.02170),
    "sixth street nw": (38.91895, -77.02152),
    "6th street nw": (38.91895, -77.02152),
    "500 block of w street nw": (38.91920, -77.02110),
    "500 block w street nw": (38.91920, -77.02110),
    "200 block of v street nw": (38.91807, -77.01948),
    "200 block of v street n.w": (38.91807, -77.01948),
    "500 block of college street nw": (38.92190, -77.02105),
    "2500 block of georgia ave": (38.92410, -77.02190),
    "2500 block of georgia ave nw": (38.92410, -77.02190),
    "600 block of howard place nw": (38.92330, -77.02130),
}

EMAIL_NOISE_PATTERNS = [
    r"preliminary investigation is being conducted.*",
    r"no further information at this time.*",
    r"please avoid the area\.?",
    r"this is howard related\.?",
    r"this is non-howard related\.?",
]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def deduplicate_repeated_message(text: str) -> str:
    text = normalize_whitespace(text)
    half = len(text) // 2
    if half > 50:
        first = text[:half].strip()
        second = text[half:].strip()
        if first and second and first[:120] == second[:120]:
            return first
    return text


def clean_email_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = deduplicate_repeated_message(text)
    text = normalize_whitespace(text)
    text = re.sub(r"This is a message from.*?(?=[A-Z])", "", text, flags=re.IGNORECASE)
    for pattern in EMAIL_NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return normalize_whitespace(text)


def classify_text(text: str) -> str:
    text = str(text).lower()
    scores = {category: 0 for category in CATEGORY_KEYWORDS}
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[category] += 1
    best_category = max(scores, key=scores.get)
    return best_category if scores[best_category] > 0 else "Other"


LOCATION_PATTERNS = [
    r"near\s+(?:the\s+)?((?:\d+\s+block\s+of\s+)?[A-Z0-9][A-Za-z0-9.&\- ]+?(?:NW|NE|SW|SE))(?=\s+at\s+\d|[\.,;]|$)",
    r"near\s+([A-Z][A-Za-z0-9.&\- ]+?)(?=\s+at\s+\d|[\.,;]|$)",
    r"at\s+([A-Z][A-Za-z0-9.&\- ]+?)(?=\s+at\s+\d|[\.,;]|$)",
    r"on\s+((?:\d+\s+block\s+of\s+)?[A-Z0-9][A-Za-z0-9.&\- ]+?(?:NW|NE|SW|SE))(?=[\.,;]|$)",
    r"in\s+([A-Z][A-Za-z0-9.&\- ]+?)(?=[\.,;]|$)",
    r"in\s+(?:the\s+)?([A-Za-z0-9.&\- ]+)",
]


def extract_location(text: str) -> str:
    if not isinstance(text, str):
        return ""

    cleaned = normalize_whitespace(text)

    cleaned = re.sub(r"\bN\.?W\.?\b", "NW", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bN\.?E\.?\b", "NE", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bS\.?W\.?\b", "SW", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bS\.?E\.?\b", "SE", cleaned, flags=re.IGNORECASE)

    lower_cleaned = cleaned.lower()

    # direct slang / shorthand handling
    slang_locations = {
        "towers": "Howard Plaza Towers",
        "in towers": "Howard Plaza Towers",
        "at towers": "Howard Plaza Towers",
        "the towers": "Howard Plaza Towers",
        "yard": "The Yard",
        "in the yard": "The Yard",
        "the yard": "The Yard",
        "blackburn": "Blackburn Center",
        "founders": "Founders Library",
        "chemistry building": "Chemistry Building",
    }

    for phrase, mapped_location in slang_locations.items():
        if phrase in lower_cleaned:
            return mapped_location

    dual_block_match = re.search(
        r"near\s+the\s+(\d+\s+block\s+of\s+[A-Za-z0-9 .]+?)\s+and\s+the\s+(\d+\s+block\s+of\s+[A-Za-z0-9 .]+?(?:NW|NE|SW|SE))(?=\s+at\s+\d|[.,;]|$)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if dual_block_match:
        first = dual_block_match.group(1).strip(" .,;:")
        second = dual_block_match.group(2).strip(" .,;:")
        return second if second else first

    # extra patterns for more casual language like "in towers"
    location_patterns = [
        r"near\s+(?:the\s+)?((?:\d+\s+block\s+of\s+)?[A-Z0-9][A-Za-z0-9.&\- ]+?(?:NW|NE|SW|SE))(?=\s+at\s+\d|[\.,;]|$)",
        r"near\s+([A-Z][A-Za-z0-9.&\- ]+?)(?=\s+at\s+\d|[\.,;]|$)",
        r"at\s+([A-Z][A-Za-z0-9.&\- ]+?)(?=\s+at\s+\d|[\.,;]|$)",
        r"on\s+((?:\d+\s+block\s+of\s+)?[A-Z0-9][A-Za-z0-9.&\- ]+?(?:NW|NE|SW|SE))(?=[\.,;]|$)",
        r"in\s+(?:the\s+)?([A-Z][A-Za-z0-9.&\- ]+?)(?=[\.,;]|$)",
        r"\b(?:in|at)\s+(towers|yard|blackburn|founders|chemistry building)\b",
    ]

    for pattern in location_patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            location = match.group(1).strip(" .,;:")
            location = re.sub(r"^the\s+", "", location, flags=re.IGNORECASE)

            if " and the " in location.lower():
                parts = re.split(r"\s+and\s+the\s+", location, flags=re.IGNORECASE)
                location = parts[-1].strip(" .,;:")

            # normalize short campus names
            normalized_map = {
                "towers": "Howard Plaza Towers",
                "yard": "The Yard",
                "blackburn": "Blackburn Center",
                "founders": "Founders Library",
                "chemistry building": "Chemistry Building",
            }

            location_key = location.lower()
            if location_key in normalized_map:
                return normalized_map[location_key]

            if len(location) > 2:
                return location

    return ""


@st.cache_data(show_spinner=False)
def load_default_data() -> pd.DataFrame:
    path = Path(__file__).parent / "data" / "sample_alerts.csv"
    return pd.read_csv(path)


@st.cache_resource(show_spinner=False)
def get_geocoder():
    geolocator = Nominatim(user_agent="campus_safety_language_map")
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)


def normalize_location_key(location: str) -> str:
    location = str(location).lower().strip()
    location = re.sub(r"\bn\.?w\.?\b", "nw", location)
    location = re.sub(r"\bn\.?e\.?\b", "ne", location)
    location = re.sub(r"\bs\.?w\.?\b", "sw", location)
    location = re.sub(r"\bs\.?e\.?\b", "se", location)
    location = re.sub(r"\s+", " ", location)
    return location.strip(" .,;:")


@lru_cache(maxsize=256)
def geocode_location(location: str):
    if not location:
        return None, None

    normalized = normalize_location_key(location)

    if normalized in KNOWN_COORDINATES:
        return KNOWN_COORDINATES[normalized]

    query = KNOWN_LOCATIONS.get(normalized, f"{location}, {DEFAULT_CITY}")
    geocode = get_geocoder()

    try:
        result = geocode(query)
    except Exception:
        result = None

    if result:
        return result.latitude, result.longitude

    return None, None


@st.cache_data(show_spinner=False)
def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    if "description" not in work.columns:
        work["description"] = ""

    work["description"] = work["description"].fillna("").map(clean_email_text)

    if "location" not in work.columns:
        work["location"] = work["description"].map(extract_location)
    else:
        work["location"] = work["location"].fillna("")
        missing = work["location"].eq("")
        work.loc[missing, "location"] = work.loc[missing, "description"].map(extract_location)

    if "date" not in work.columns:
        work["date"] = pd.NaT
    work["date"] = pd.to_datetime(work["date"], errors="coerce")

    if "category" not in work.columns:
        work["category"] = work["description"].map(classify_text)
    else:
        work["category"] = work["category"].fillna("").replace("", pd.NA)
        work["category"] = work["category"].fillna(work["description"].map(classify_text))

    coords = work["location"].map(geocode_location)
    work["lat"] = [c[0] for c in coords]
    work["lon"] = [c[1] for c in coords]

    return work


def build_map(df: pd.DataFrame) -> folium.Map:
    m = folium.Map(location=CAMPUS_CENTER, zoom_start=15, tiles="CartoDB positron")
    cluster = MarkerCluster().add_to(m)

    color_map = {
        "Sexual Misconduct": "pink",
        "Theft": "blue",
        "Violence": "red",
        "Suspicious Activity": "orange",
        "Safety Hazard": "green",
        "Vehicle Incident": "purple",
        "Other": "gray",
    }

    for _, row in df.dropna(subset=["lat", "lon"]).iterrows():
        popup = folium.Popup(
            f"<b>Category:</b> {row['category']}<br>"
            f"<b>Location:</b> {row['location']}<br>"
            f"<b>Date:</b> {row['date'].date() if pd.notnull(row['date']) else 'Unknown'}<br>"
            f"<b>Description:</b> {row['description']}",
            max_width=350,
        )
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=popup,
            icon=folium.Icon(color=color_map.get(row["category"], "gray"), icon="info-sign"),
        ).add_to(cluster)

    return m


st.title("Campus Safety Language Map")
st.caption(
    "A Streamlit web app that classifies campus safety text and visualizes incidents on an interactive map."
)

with st.sidebar:
    st.header("Data Input")
    uploaded = st.file_uploader("Upload a CSV", type=["csv"])
    st.markdown(
        "Required column: `description`  \nOptional columns: `location`, `date`, `category`"
    )
    st.divider()
    st.header("Report a New Incident")
    raw_email = st.text_area("Paste/Type Here", height=260)
    parse_now = st.button("Add it to the dataset")

if uploaded is not None:
    source_df = pd.read_csv(uploaded)
else:
    source_df = load_default_data()

parsed_preview = None
if raw_email.strip():
    cleaned_preview = clean_email_text(raw_email)
    extracted_location = extract_location(cleaned_preview)
    preview_lat, preview_lon = geocode_location(extracted_location)

    parsed_preview = {
        "description": cleaned_preview,
        "location": extracted_location,
        "category": classify_text(cleaned_preview),
        "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "lat": preview_lat,
        "lon": preview_lon,
    }

if parse_now and parsed_preview:
    source_df = pd.concat(
        [
            source_df,
            pd.DataFrame(
                [
                    {
                        "description": parsed_preview["description"],
                        "location": parsed_preview["location"],
                        "date": parsed_preview["date"],
                        "category": parsed_preview["category"],
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

with st.spinner("Processing incident text and geocoding locations..."):
    df = enrich_dataframe(source_df)

left, right = st.columns([2, 1])

with right:
    st.subheader("Filters")
    categories = sorted(df["category"].dropna().unique().tolist())
    selected_categories = st.multiselect("Incident categories", categories, default=categories)

    min_date = df["date"].min()
    max_date = df["date"].max()
    if pd.notnull(min_date) and pd.notnull(max_date):
        date_range = st.date_input("Date range", value=(min_date.date(), max_date.date()))
        if len(date_range) == 2:
            start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            filtered_df = df[
                df["category"].isin(selected_categories)
                & (df["date"].isna() | ((df["date"] >= start_date) & (df["date"] <= end_date)))
            ]
        else:
            filtered_df = df[df["category"].isin(selected_categories)]
    else:
        filtered_df = df[df["category"].isin(selected_categories)]

    st.subheader("Summary")
    st.metric("Total incidents", len(filtered_df))
    st.metric("Mapped incidents", filtered_df[["lat", "lon"]].dropna().shape[0])
    st.metric("Unique locations", filtered_df["location"].replace("", pd.NA).dropna().nunique())

    st.subheader("Incident Counts")
    st.bar_chart(filtered_df["category"].value_counts())

    if parsed_preview:
        st.subheader("Parsed Email Preview")
        st.write(parsed_preview)

with left:
    st.subheader("Interactive Map")
    folium_map = build_map(filtered_df)
    html(folium_map._repr_html_(), height=650)

st.subheader("Incident Table")
st.dataframe(
    filtered_df[["date", "category", "location", "description", "lat", "lon"]],
    use_container_width=True,
    hide_index=True,
)

st.subheader("How to Use")
st.markdown(
    """
1. Type or paste campus safety alert text into the sidebar input box.
2. Click "Add it to the dataset" to submit the incident.
3. The app will clean the text, classify the incident, extract the location, geocode it, and plot it.
4. Use the filters to explore incidents by type and date.
"""
)
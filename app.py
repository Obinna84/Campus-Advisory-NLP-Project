from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html

from campus_safety.data import enrich_dataframe, load_default_data
from campus_safety.visuals import build_map

st.set_page_config(page_title="Campus Advisory NLP Project", layout="wide")


@st.cache_data(show_spinner=False)
def load_uploaded_csv(uploaded_file) -> pd.DataFrame:
    return pd.read_csv(uploaded_file, encoding="latin-1")


st.title("NLP Campus Safety Map")
st.caption(
    "Classify incident reports, extract locations, and visualize campus safety patterns with a cleaner NLP + mapping workflow."
)

with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Upload a CSV", type=["csv"])
    st.markdown("Required column: `description`  \\nOptional columns: `location`, `date`, `category`")
    use_sample = st.toggle("Use bundled sample dataset", value=uploaded is None)

    st.divider()
    st.header("Add one incident")
    raw_incident = st.text_area("Paste a report", height=220, placeholder="Paste a safety alert or incident report here...")
    add_incident = st.button("Append report")

if uploaded is not None and not use_sample:
    source_df = load_uploaded_csv(uploaded)
else:
    source_df = load_default_data()

pending_row = None
if raw_incident.strip():
    preview_df = enrich_dataframe(pd.DataFrame([{"description": raw_incident}]))
    pending_row = preview_df.iloc[0].to_dict()

if add_incident and pending_row is not None:
    new_row = {
        "description": pending_row["description"],
        "location": pending_row["location"],
        "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "category": pending_row["incident_type"],
    }
    source_df = pd.concat([source_df, pd.DataFrame([new_row])], ignore_index=True)

with st.spinner("Processing incidents..."):
    df = enrich_dataframe(source_df)

left_col, right_col = st.columns([1.9, 1.1])

with right_col:
    st.subheader("Filters")
    family_options = sorted(df["incident_family"].dropna().unique().tolist())
    selected_families = st.multiselect("Incident families", family_options, default=family_options)

    type_options = sorted(df["incident_type"].dropna().unique().tolist())
    selected_types = st.multiselect("Incident types", type_options, default=type_options)

    location_query = st.text_input("Search location or text")

    min_date = df["date"].min()
    max_date = df["date"].max()
    filtered_df = df.copy()

    if selected_families:
        filtered_df = filtered_df[filtered_df["incident_family"].isin(selected_families)]
    if selected_types:
        filtered_df = filtered_df[filtered_df["incident_type"].isin(selected_types)]
    if location_query.strip():
        search_mask = (
            filtered_df["location"].fillna("").str.contains(location_query, case=False)
            | filtered_df["description"].fillna("").str.contains(location_query, case=False)
        )
        filtered_df = filtered_df[search_mask]

    if pd.notnull(min_date) and pd.notnull(max_date):
        date_range = st.date_input("Date range", value=(min_date.date(), max_date.date()))
        if len(date_range) == 2:
            start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            filtered_df = filtered_df[
                filtered_df["date"].isna() | ((filtered_df["date"] >= start_date) & (filtered_df["date"] <= end_date))
            ]

    st.subheader("Snapshot")
    st.metric("Total incidents", f"{len(filtered_df):,}")
    st.metric("Mapped incidents", f"{filtered_df[['lat', 'lon']].dropna().shape[0]:,}")
    st.metric("Unique locations", f"{filtered_df['location'].replace('', pd.NA).dropna().nunique():,}")

    if not filtered_df.empty:
        top_type = filtered_df["incident_type"].value_counts().idxmax()
        st.metric("Most common type", top_type)

    if pending_row is not None:
        st.subheader("Parsed preview")
        st.json(
            {
                "incident_type": pending_row.get("incident_type"),
                "incident_family": pending_row.get("incident_family"),
                "location": pending_row.get("location"),
                "confidence": pending_row.get("model_confidence"),
                "source": pending_row.get("classification_source"),
            }
        )

with left_col:
    metric_cols = st.columns(3)
    if not filtered_df.empty:
        metric_cols[0].metric("Violence", int((filtered_df["incident_family"] == "Violence").sum()))
        metric_cols[1].metric("Vehicle", int((filtered_df["incident_family"] == "Vehicle Incident").sum()))
        metric_cols[2].metric("Safety", int((filtered_df["incident_family"] == "Safety Hazard").sum()))
    else:
        metric_cols[0].metric("Violence", 0)
        metric_cols[1].metric("Vehicle", 0)
        metric_cols[2].metric("Safety", 0)

    st.subheader("Interactive map")
    folium_map = build_map(filtered_df)
    html(folium_map._repr_html_(), height=650)

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.subheader("Incident families")
        if filtered_df.empty:
            st.info("No incidents match the current filters.")
        else:
            st.bar_chart(filtered_df["incident_family"].value_counts())
    with chart_right:
        st.subheader("Incident types")
        if filtered_df.empty:
            st.info("No incidents match the current filters.")
        else:
            st.bar_chart(filtered_df["incident_type"].value_counts().head(10))

st.subheader("Incident table")
st.dataframe(
    filtered_df[
        [
            "date",
            "incident_family",
            "incident_type",
            "location",
            "model_confidence",
            "classification_source",
            "description",
            "lat",
            "lon",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

with st.expander("How this version is improved"):
    st.markdown(
        """
- Cleaner data pipeline with reusable modules.
- Better classification flow: spaCy if available, keyword fallback if not.
- Stronger location extraction with campus aliases, block detection, intersections, and geocoding cache.
- Better filters, search, confidence scores, and summary metrics.
- Incident family + incident type views for cleaner analysis.
        """
    )

footer_path = Path("README.md")
if footer_path.exists():
    st.caption("Tip: see the README for setup, architecture, and extension ideas.")

from __future__ import annotations

import folium
import pandas as pd
from folium.plugins import MarkerCluster

from .config import CAMPUS_CENTER, FAMILY_COLOR_MAP


def build_map(df: pd.DataFrame) -> folium.Map:
    map_obj = folium.Map(location=CAMPUS_CENTER, zoom_start=14, tiles="CartoDB positron")
    cluster = MarkerCluster().add_to(map_obj)

    for _, row in df.dropna(subset=["lat", "lon"]).iterrows():
        popup = folium.Popup(
            (
                f"<b>Incident type:</b> {row.get('incident_type', 'Unknown')}<br>"
                f"<b>Family:</b> {row.get('incident_family', 'Unknown')}<br>"
                f"<b>Location:</b> {row.get('location', 'Unknown')}<br>"
                f"<b>Date:</b> {row['date'].date() if pd.notnull(row.get('date')) else 'Unknown'}<br>"
                f"<b>Confidence:</b> {row.get('model_confidence', 0):.2f}<br>"
                f"<b>Description:</b> {row.get('description', '')}"
            ),
            max_width=380,
        )
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=popup,
            tooltip=f"{row.get('incident_type', 'Incident')} | {row.get('location', 'Unknown')}",
            icon=folium.Icon(
                color=FAMILY_COLOR_MAP.get(str(row.get("incident_family", "Other")), "gray"),
                icon="info-sign",
            ),
        ).add_to(cluster)

    return map_obj

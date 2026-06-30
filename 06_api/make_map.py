"""
Visualisasikan merged_venues_enriched.csv ke peta interaktif DKI Jakarta.

Output: data/map_jakarta.html (buka di browser)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import folium
from folium.plugins import MarkerCluster

import config

COLOR_BY_PREFIX = {
    "tourism": "blue",
    "leisure": "green",
    "historic": "orange",
    "amenity": "purple",
}


def category_color(cat):
    prefix = cat.split(":", 1)[0]
    return COLOR_BY_PREFIX.get(prefix, "gray")


def main():
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)

    center = [df["latitude"].mean(), df["longitude"].mean()]
    m = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
    cluster = MarkerCluster().add_to(m)

    for _, row in df.iterrows():
        popup = (
            f"<b>{row['name']}</b><br>"
            f"Kategori: {row['venue_category']}<br>"
            f"Jam buka: {row.get('Senin_buka', '-')}–{row.get('Senin_tutup', '-')} (Senin)<br>"
            f"Rating: {row.get('google_rating', '-')} ({row.get('google_rating_count', '-')} ulasan)<br>"
            f"<a href='{row.get('References', '#')}' target='_blank'>Referensi</a>"
        )
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=4,
            color=category_color(row["venue_category"]),
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup, max_width=300),
        ).add_to(cluster)

    out_path = "data/map_jakarta.html"
    m.save(out_path)
    print(f"Tersimpan -> {out_path} ({len(df)} venue)")


if __name__ == "__main__":
    main()

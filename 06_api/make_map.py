"""
Visualisasikan jakarta_tourism_venues_clustered.csv ke peta interaktif DKI Jakarta.
Warna marker per kategori STEPS, popup menampilkan field Google Places lengkap.

Output: data/processed/cluster_map.html
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import folium
from folium.plugins import MarkerCluster

import config

# Warna per kategori STEPS
CATEGORY_COLOR = {
    "Museum":                       "#2196F3",   # biru
    "History Museum":               "#1565C0",   # biru tua
    "Art Museum":                   "#9C27B0",   # ungu
    "Science Museum":               "#00BCD4",   # cyan
    "Temple":                       "#FF9800",   # oranye
    "Historic Site":                "#795548",   # coklat
    "Beach":                        "#00BFA5",   # teal
    "Zoo":                          "#4CAF50",   # hijau
    "Aquarium":                     "#0288D1",   # biru muda
    "Theme Park":                   "#F44336",   # merah
    "Theme Park Ride / Attraction": "#E91E63",   # pink
    "Monument / Landmark":          "#607D8B",   # abu-abu biru
}
DEFAULT_COLOR = "#9E9E9E"

ZONE_COLORS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45",
]


def hex_to_folium(hex_color):
    return hex_color


def main():
    df = pd.read_csv(config.CLUSTERED_VENUES_CSV)
    print(f"Total venue: {len(df)}")

    center = [df["latitude"].mean(), df["longitude"].mean()]
    m = folium.Map(location=center, zoom_start=12, tiles="OpenStreetMap")

    # Layer per zone (toggle)
    zone_layers = {}
    for zone_id in sorted(df["zone_id"].unique()):
        fg = folium.FeatureGroup(name=f"Zone {zone_id}", show=True)
        zone_layers[zone_id] = fg
        fg.add_to(m)

    # MarkerCluster per zone
    clusters = {}
    for zone_id, fg in zone_layers.items():
        mc = MarkerCluster(
            options={"maxClusterRadius": 40, "disableClusteringAtZoom": 15}
        )
        mc.add_to(fg)
        clusters[zone_id] = mc

    for _, row in df.iterrows():
        cat = row.get("venue_category", "")
        color = CATEGORY_COLOR.get(cat, DEFAULT_COLOR)
        zone_id = int(row.get("zone_id", 0))
        zone_color = ZONE_COLORS[zone_id % len(ZONE_COLORS)]

        rating = row.get("google_rating")
        rating_str = f"{rating:.1f}★" if pd.notna(rating) else "N/A"
        rating_count = row.get("google_rating_count")
        rating_count_str = f"({int(rating_count):,} ulasan)" if pd.notna(rating_count) else ""

        sublocality = row.get("sublocality", "")
        locality = row.get("locality", "")
        lokasi_str = ""
        if pd.notna(sublocality) and sublocality:
            lokasi_str = str(sublocality)
            if pd.notna(locality) and locality:
                lokasi_str += f", {locality}"
        elif pd.notna(locality) and locality:
            lokasi_str = str(locality)

        business_status = row.get("business_status", "")
        status_badge = ""
        if pd.notna(business_status):
            if business_status == "OPERATIONAL":
                status_badge = '<span style="color:green">● Buka</span>'
            elif business_status == "CLOSED_TEMPORARILY":
                status_badge = '<span style="color:orange">● Sementara Tutup</span>'
            elif business_status == "CLOSED_PERMANENTLY":
                status_badge = '<span style="color:red">● Tutup Permanen</span>'

        desc = row.get("description", "")
        desc_str = f'<br><i style="color:#666;font-size:11px">{str(desc)[:120]}...</i>' if pd.notna(desc) and desc else ""

        checkin = row.get("checkin_count", 0)
        checkin_str = f"{int(checkin):,}" if pd.notna(checkin) else "0"

        ref = row.get("References", "")
        ref_link = f'<br><a href="{ref}" target="_blank" style="font-size:11px">🔗 Referensi</a>' if pd.notna(ref) and ref else ""

        wheelchair = row.get("wheelchair_accessible")
        parking = row.get("has_parking")
        restroom = row.get("has_restroom")
        facilities = []
        if pd.notna(wheelchair) and wheelchair:
            facilities.append("♿ Aksesibel")
        if pd.notna(parking) and parking:
            facilities.append("🅿️ Parkir")
        if pd.notna(restroom) and restroom:
            facilities.append("🚻 Toilet")
        facilities_str = " · ".join(facilities) if facilities else ""

        popup_html = f"""
<div style="font-family:Arial,sans-serif;min-width:220px;max-width:300px">
  <b style="font-size:13px">{row['name']}</b>
  <br><span style="background:{color};color:white;padding:1px 6px;border-radius:3px;font-size:11px">{cat}</span>
  <span style="background:{zone_color};color:white;padding:1px 6px;border-radius:3px;font-size:11px;margin-left:4px">Zone {zone_id}</span>
  <br><br>
  {status_badge}
  <br>⭐ {rating_str} {rating_count_str}
  <br>📍 {lokasi_str if lokasi_str else row.get('address', '-')}
  <br>🏃 {checkin_str} check-in
  {desc_str}
  <br><br>
  <b>Jam Senin:</b> {row.get('Senin_buka','-')} – {row.get('Senin_tutup','-')}
  <br><b>Jam Sabtu:</b> {row.get('Sabtu_buka','-')} – {row.get('Sabtu_tutup','-')}
  <br><b>Jam Minggu:</b> {row.get('Minggu_buka','-')} – {row.get('Minggu_tutup','-')}
  {'<br>' + facilities_str if facilities_str else ''}
  {ref_link}
</div>"""

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=7,
            color=zone_color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            weight=2,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{row['name']} ({cat})",
        ).add_to(clusters[zone_id])

    # Legend kategori
    legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
            padding:12px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.3);
            font-family:Arial,sans-serif;font-size:12px;max-height:400px;overflow-y:auto">
  <b>Kategori</b><br>"""
    for cat, color in CATEGORY_COLOR.items():
        legend_html += f'<span style="background:{color};color:white;padding:1px 8px;border-radius:3px;display:inline-block;margin:2px 0">{cat}</span><br>'
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))

    # Legend zone
    zone_legend = """
<div style="position:fixed;bottom:30px;right:30px;z-index:1000;background:white;
            padding:12px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.3);
            font-family:Arial,sans-serif;font-size:12px">
  <b>Zone (border marker)</b><br>"""
    for i, color in enumerate(ZONE_COLORS):
        zone_legend += f'<span style="background:{color};color:white;padding:1px 8px;border-radius:3px;display:inline-block;margin:2px 0">Zone {i}</span><br>'
    zone_legend += "</div>"
    m.get_root().html.add_child(folium.Element(zone_legend))

    folium.LayerControl(collapsed=False).add_to(m)

    out_path = os.path.join(os.path.dirname(config.CLUSTERED_VENUES_CSV), "cluster_map.html")
    m.save(out_path)
    print(f"Tersimpan -> {out_path} ({len(df)} venue)")


if __name__ == "__main__":
    main()

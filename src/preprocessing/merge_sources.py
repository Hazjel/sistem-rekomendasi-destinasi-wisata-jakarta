"""
Gabung Massive-STEPS (tulang punggung: POI nyata + checkin_count popularitas
asli) dengan OSM (enrichment: opening_hours, link referensi) by koordinat
berdekatan.

Match radius config.MERGE_RADIUS_M (default 150m, lebih sempit dari
cluster-dedupe OSM 700m karena ini cross-dataset matching, bukan dedupe
sesama OSM -- 2 sumber beda kemungkinan titik koordinat venue yang sama
sedikit bergeser).

Venue Massive-STEPS yang match -> dilengkapi opening_hours/wikipedia/website
dari OSM. Yang tidak match -> tetap masuk, kolom OSM default kosong
(hours_source=default, sama pola seperti enrich.py).

Output: data/processed/merged_venues.csv
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config


def _haversine_m_vec(lat1, lon1, lat2, lon2):
    """Haversine vectorized (numpy) -- lat1/lon1 skalar, lat2/lon2 array."""
    r = 6371000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def find_nearest_osm_idx(lat, lon, osm_lat, osm_lon, radius_m):
    """Index OSM row terdekat dalam radius_m, None kalau tidak ada."""
    dists = _haversine_m_vec(lat, lon, osm_lat, osm_lon)
    idx_min = np.argmin(dists)
    if dists[idx_min] <= radius_m:
        return idx_min
    return None


def main():
    steps = pd.read_csv(config.STEPS_FILTERED_CSV)
    n_steps = len(steps)
    print(f"Venue Massive-STEPS (filtered): {n_steps}")

    DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    day_cols = [f"{d}_buka" for d in DAYS_ID] + [f"{d}_tutup" for d in DAYS_ID]

    # OSM enriched dipakai untuk osm_url + References saja.
    # Kalau file tidak ada (sudah dihapus), skip OSM matching —
    # jam buka diisi enrich_hours_google.py di step berikutnya.
    if os.path.exists(config.CLEAN_CSV):
        osm = pd.read_csv(config.CLEAN_CSV)
        print(f"Venue OSM (clean, kandidat match): {len(osm)}")
        osm_lat = osm["latitude"].to_numpy()
        osm_lon = osm["longitude"].to_numpy()

        matched_cols = {c: [] for c in ["osm_url", "References", "hours_source"] + day_cols}
        n_match = 0
        for _, row in steps.iterrows():
            idx = find_nearest_osm_idx(row["latitude"], row["longitude"],
                                        osm_lat, osm_lon, config.MERGE_RADIUS_M)
            if idx is not None:
                n_match += 1
                nearest = osm.iloc[idx]
                matched_cols["osm_url"].append(nearest.get("osm_url", "") or "")
                matched_cols["References"].append(nearest.get("References", "") or "")
                matched_cols["hours_source"].append(nearest.get("hours_source", "default"))
                for dc in day_cols:
                    matched_cols[dc].append(nearest.get(dc, "Tutup") or "Tutup")
            else:
                matched_cols["osm_url"].append("")
                matched_cols["References"].append("")
                matched_cols["hours_source"].append("default")
                for dc in day_cols:
                    matched_cols[dc].append("Tutup")

        for c, vals in matched_cols.items():
            steps[c] = vals

        pct_match = n_match / n_steps if n_steps else 0
        print(f"\nBerhasil match ke OSM: {n_match}/{n_steps} ({pct_match:.1%})")
        print(f"Tidak match (kolom OSM default/kosong): {n_steps - n_match}")
    else:
        print("venues_osm_clean.csv tidak ada — skip OSM matching.")
        print("Jam buka akan diisi enrich_hours_google.py.")
        steps["osm_url"] = ""
        steps["References"] = ""
        steps["hours_source"] = "default"
        for dc in day_cols:
            steps[dc] = "Tutup"

    os.makedirs(os.path.dirname(config.MERGED_VENUES_CSV), exist_ok=True)
    steps.to_csv(config.MERGED_VENUES_CSV, index=False)
    print(f"\nVenue final setelah merge: {len(steps)}")
    print(f"Tersimpan -> {config.MERGED_VENUES_CSV}")


if __name__ == "__main__":
    main()

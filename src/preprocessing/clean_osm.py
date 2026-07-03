"""
Preprocessing venue OSM: baca raw -> dedupe -> cluster-dedupe -> simpan clean.

Step yang dilakukan (semua dicatat before/after):
  1. Dedupe exact: buang baris duplikat (nama + koordinat ~4dp sama persis)
     -> terjadi karena node & way OSM bisa overlap di titik yang sama.
  2. Cluster-dedupe: gabung entitas OSM beda yang sebenarnya venue sama
     (cth 4 gerbang Monas + Taman Monas = 1 destinasi).
     Hanya utk kategori tourism/leisure/historic (amenity skip, terlalu banyak).

Input:  data/raw/venues_osm_raw.csv
Output: data/processed/venues_osm_clean.csv
"""
import os
import sys
from math import radians, sin, cos, asin, sqrt

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config


# --- Dedupe OSM (dulu di 01_data_collection/collect_osm.py, di-inline agar mandiri) ---
def dedupe(rows):
    """Buang duplikat nama+koordinat (node & way bisa overlap)."""
    seen, out = set(), []
    for r in rows:
        key = (r["name"].strip().lower(), round(r["latitude"], 4), round(r["longitude"], 4))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


_GENERIC_WORDS = {
    "taman", "museum", "monumen", "patung", "lapangan", "kawasan", "gedung",
    "anjungan", "menara", "tugu", "park", "playground", "garden", "blok",
    "kompleks", "komplek", "pertigaan", "ruang", "habitat", "jogging", "kota",
}


def _shared_word(name_a, name_b):
    wa = {w for w in name_a.lower().split() if len(w) > 3 and w not in _GENERIC_WORDS}
    wb = {w for w in name_b.lower().split() if len(w) > 3 and w not in _GENERIC_WORDS}
    return bool(wa & wb)


def _row_priority(r):
    has_ref = bool(r["website"] or r["wikipedia"] or r["wikidata"])
    specific_category = not r["venue_category"].endswith(":yes")
    return (specific_category, has_ref, len(r["name"]))


def dedupe_clusters(rows, radius_m=700):
    """Gabung venue beda nama tapi entitas sama (cth 4 gerbang Monas jadi 1)."""
    n = len(rows)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dist = _haversine_m(rows[i]["latitude"], rows[i]["longitude"],
                                rows[j]["latitude"], rows[j]["longitude"])
            if dist <= radius_m and _shared_word(rows[i]["name"], rows[j]["name"]):
                adj[i].append(j)
                adj[j].append(i)

    visited = [False] * n
    out = []
    for i in range(n):
        if visited[i]:
            continue
        stack, cluster_idx = [i], []
        visited[i] = True
        while stack:
            cur = stack.pop()
            cluster_idx.append(cur)
            for nb in adj[cur]:
                if not visited[nb]:
                    visited[nb] = True
                    stack.append(nb)
        cluster = [rows[k] for k in cluster_idx]
        out.append(max(cluster, key=_row_priority))
    return out


def main():
    df = pd.read_csv(config.RAW_CSV)
    n_raw = len(df)
    print(f"[INPUT] Venue OSM mentah: {n_raw}")

    # Step 1: dedupe exact (nama + koordinat ~4dp)
    rows = df.to_dict("records")
    rows_deduped = dedupe(rows)
    n_after_dedupe = len(rows_deduped)
    print(f"\n[STEP 1] Dedupe exact (nama + koordinat sama):")
    print(f"  sebelum : {n_raw}")
    print(f"  sesudah : {n_after_dedupe} ({n_raw - n_after_dedupe} duplikat dibuang)")

    # Step 2: cluster-dedupe (entitas beda, venue sama -- cth gerbang Monas)
    clusterable = [r for r in rows_deduped if not r["venue_category"].startswith("amenity:")]
    rest = [r for r in rows_deduped if r["venue_category"].startswith("amenity:")]
    clustered = dedupe_clusters(clusterable)
    rows_clean = clustered + rest
    n_clean = len(rows_clean)
    print(f"\n[STEP 2] Cluster-dedupe (gabung entitas OSM = 1 venue):")
    print(f"  sebelum : {n_after_dedupe}")
    print(f"  sesudah : {n_clean} ({n_after_dedupe - n_clean} entitas digabung)")
    print(f"  contoh  : 4 gerbang Monas + Taman Monas -> 1 row 'Taman Monas'")

    os.makedirs("data/processed", exist_ok=True)
    out = pd.DataFrame(rows_clean)
    out.to_csv(config.CLEAN_CSV, index=False)
    print(f"\nTersimpan -> {config.CLEAN_CSV} ({n_clean} venue)")


if __name__ == "__main__":
    main()

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

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../01_data_collection"))
import config
from collect_osm import dedupe, dedupe_clusters


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

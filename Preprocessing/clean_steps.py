"""
Preprocessing Massive-STEPS-Jakarta: baca raw -> cleaning -> agregasi per venue.

Step yang dilakukan (semua dicatat before/after):
  1. Drop baris null lat/lon/name (venue tidak bisa dipakai tanpa koordinat/nama).
  2. Agregasi per venue_id: 1 row/venue, checkin_count = proxy popularitas nyata.

Input:  data/raw/jakarta_checkins_raw.csv     (mentah, 412.100 row)
Output:
    data/processed/steps_checkins_clean.csv  (level check-in, sudah drop null)
    data/processed/steps_venues_raw.csv      (level venue, 1 row/venue)
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def main():
    raw_path = "data/raw/jakarta_checkins_raw.csv"
    df = pd.read_csv(raw_path)
    n_raw = len(df)
    print(f"[INPUT] Check-in mentah: {n_raw}")
    print(f"  kolom null:")
    print(df.isnull().sum()[df.isnull().sum() > 0].to_string())

    # Step 1: drop null lat/lon/name
    df_clean = df.dropna(subset=["latitude", "longitude", "name"]).copy()
    n_clean = len(df_clean)
    print(f"\n[STEP 1] Drop null lat/lon/name:")
    print(f"  sebelum : {n_raw}")
    print(f"  sesudah : {n_clean} ({n_raw - n_clean} dibuang, {(n_raw - n_clean)/n_raw:.1%})")

    os.makedirs("data/processed", exist_ok=True)
    checkins_out = "data/processed/steps_checkins_clean.csv"
    df_clean.to_csv(checkins_out, index=False)
    print(f"  tersimpan -> {checkins_out}")

    # Step 2: agregasi per venue (1 row/venue)
    venues = (
        df_clean.groupby("venue_id")
        .agg(
            name=("name", "first"),
            venue_category=("venue_category", "first"),
            latitude=("latitude", "first"),
            longitude=("longitude", "first"),
            address=("address", "first"),
            checkin_count=("venue_id", "count"),
            last_checkin=("timestamp", "max"),
        )
        .reset_index()
    )
    print(f"\n[STEP 2] Agregasi per venue (1 row/venue):")
    print(f"  check-in clean : {n_clean}")
    print(f"  venue unik     : {len(venues)}")
    print(f"  top kategori   :")
    print(venues["venue_category"].value_counts().head(5).to_string())

    venues_out = config.STEPS_VENUES_RAW_CSV
    venues.to_csv(venues_out, index=False)
    print(f"  tersimpan -> {venues_out}")


if __name__ == "__main__":
    main()

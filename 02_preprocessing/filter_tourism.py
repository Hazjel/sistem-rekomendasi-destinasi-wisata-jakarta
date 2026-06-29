"""
Filter venue Massive-STEPS ke kategori wisata saja (whitelist manual).

Dataset mentah didominasi Shopping Mall/Home/Office/Building (check-in
Foursquare-style umum, bukan khusus wisata) -- filter ke 23 kategori
wisata-relevan di config.STEPS_TOURISM_CATEGORIES.

Output: data/processed/steps_filtered.csv
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def main():
    df = pd.read_csv(config.STEPS_VENUES_RAW_CSV)
    n_before = len(df)
    print(f"Venue sebelum filter kategori wisata: {n_before}")
    print("Top 10 kategori (sebelum filter):")
    print(df["venue_category"].value_counts().head(10).to_string())

    filtered = df[df["venue_category"].isin(config.STEPS_TOURISM_CATEGORIES)].copy()
    n_after_cat = len(filtered)
    print(f"\nVenue setelah filter kategori wisata: {n_after_cat} "
          f"({n_after_cat / n_before:.1%} dari total)")

    name_lower = filtered["name"].str.lower().fillna("")
    mask_exclude = name_lower.apply(
        lambda n: any(kw in n for kw in config.STEPS_NAME_EXCLUDE_KEYWORDS)
    )
    excluded_sample = filtered.loc[mask_exclude, "name"].head(10).tolist()
    filtered = filtered[~mask_exclude].copy()
    n_after = len(filtered)
    print(f"Setelah keyword-exclude nama (kantor/hotel/lampu merah/dst): "
          f"{n_after} ({mask_exclude.sum()} dibuang)")
    if excluded_sample:
        print(f"  contoh yang dibuang: {excluded_sample}")

    print("\nDistribusi kategori (final):")
    print(filtered["venue_category"].value_counts().to_string())

    os.makedirs(os.path.dirname(config.STEPS_FILTERED_CSV), exist_ok=True)
    filtered.to_csv(config.STEPS_FILTERED_CSV, index=False)
    print(f"\nTersimpan -> {config.STEPS_FILTERED_CSV}")


if __name__ == "__main__":
    main()

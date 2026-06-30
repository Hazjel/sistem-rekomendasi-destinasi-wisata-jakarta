"""
Merge venue dari Google Places (venues_google_raw.csv) ke dataset utama
(merged_venues_enriched.csv).

Strategi:
1. Baca dataset existing (238 venue dari Massive-STEPS + OSM enrichment)
2. Baca venues_google_raw.csv (980 venue dari Google Places Nearby Search)
3. Dedup internal Google venues (place_id unik sudah, tapi filter by radius 100m
   untuk hilangkan venue yang lolos tipe berbeda tapi sama secara fisik)
4. Filter noise: min rating count, bukan di blacklist
5. Cari venue Google yang TIDAK overlap dengan dataset existing (radius 100m)
   -> ini venue "tambahan" yang belum ada di Massive-STEPS
6. Assign venue_id baru (format: google_XXXXX)
7. Gabung dan simpan ke merged_venues_enriched.csv

Output: data/processed/merged_venues_enriched.csv (updated)
"""
import os
import sys
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

GOOGLE_RAW = "data/raw/venues_google_raw.csv"
OVERLAP_RADIUS_M = 100  # venue dalam 100m dianggap sama

# Google Places types yang dianggap valid sebagai destinasi wisata
# Venue HARUS punya minimal 1 dari type ini di google_types
VALID_TYPES = {
    "zoo", "aquarium", "amusement_park", "water_park",
    "museum", "art_museum", "history_museum", "science_museum",
    "art_gallery",
    "monument", "historical_landmark", "historical_place",
    "cultural_landmark", "cultural_center",
    "hindu_temple", "buddhist_temple",
    "beach",
    "theme_park",
    "national_park", "wildlife_park", "wildlife_refuge",
}

# Threshold minimum rating count per kategori
# Kategori broad (Historic Site, Art Museum) butuh lebih banyak review
# agar yakin itu memang venue wisata yang dikenal publik
MIN_RATING_COUNT = {
    "Historic Site": 500,
    "Art Museum": 200,
    "Museum": 50,
    "Aquarium": 20,
    "Theme Park": 20,
    "Zoo": 20,
    "Monument / Landmark": 100,
    "Beach": 50,
    "History Museum": 20,
    "Science Museum": 20,
    "Temple": 100,
    "Theme Park Ride / Attraction": 20,
    "default": 30,
}


def haversine_m(lat1, lon1, lat2_arr, lon2_arr):
    r = 6371000
    p1, p2 = np.radians(lat1), np.radians(lat2_arr)
    dphi = np.radians(lat2_arr - lat1)
    dlmb = np.radians(lon2_arr - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def main():
    existing = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    google_raw = pd.read_csv(GOOGLE_RAW)

    n_existing = len(existing)
    n_google_raw = len(google_raw)
    print(f"Dataset existing: {n_existing} venue")
    print(f"Google raw: {n_google_raw} venue")

    # Filter noise dari Google raw
    blacklist_lower = {b.lower() for b in config.STEPS_NAME_BLACKLIST}

    # Tambah keyword exclude untuk Google venues
    google_name_exclude = config.STEPS_NAME_EXCLUDE_KEYWORDS + [
        "kos", "kost", "indekos", "apartemen", "apartment",
        "salon", "barbershop", "spa", "gym", "fitness",
        "supermarket", "minimarket", "hypermart", "carrefour",
        "pizza", "burger", "kfc", "mcdonald", "starbucks",
        "bank", "atm", "kantor pos", "puskesmas",
    ]

    mask_blacklist = google_raw["name"].str.lower().isin(blacklist_lower)
    mask_keyword = google_raw["name"].str.lower().apply(
        lambda n: any(kw in n for kw in google_name_exclude)
    )

    # Minimal ada rating (skip venue tanpa data)
    mask_no_rating = google_raw["google_rating"].isna()

    # Filter berdasarkan google_types: harus ada minimal 1 type wisata valid
    def has_valid_type(types_str):
        if not isinstance(types_str, str):
            return False
        types = {t.strip() for t in types_str.split(",")}
        return bool(types & VALID_TYPES)

    mask_invalid_type = ~google_raw["google_types"].apply(has_valid_type)

    # Filter berdasarkan minimum rating count per kategori
    def below_min_rating_count(row):
        min_count = MIN_RATING_COUNT.get(row["venue_category"],
                                         MIN_RATING_COUNT["default"])
        cnt = row.get("google_rating_count", 0) or 0
        return cnt < min_count

    mask_low_count = google_raw.apply(below_min_rating_count, axis=1)

    mask_drop = mask_blacklist | mask_keyword | mask_no_rating | mask_invalid_type | mask_low_count
    google_filtered = google_raw[~mask_drop].copy()
    print(f"\nGoogle setelah filter lengkap:")
    print(f"  - blacklist: {mask_blacklist.sum()}")
    print(f"  - keyword exclude: {mask_keyword.sum()}")
    print(f"  - no rating: {mask_no_rating.sum()}")
    print(f"  - invalid google type: {mask_invalid_type.sum()}")
    print(f"  - rating count terlalu rendah: {mask_low_count.sum()}")
    print(f"  Total dibuang: {mask_drop.sum()}, sisa: {len(google_filtered)}")

    # Dedup internal Google venues by koordinat (100m radius)
    google_filtered = google_filtered.reset_index(drop=True)
    kept = []
    seen_coords = []
    for i, row in google_filtered.iterrows():
        if not seen_coords:
            kept.append(i)
            seen_coords.append((row["latitude"], row["longitude"]))
            continue
        lats = np.array([c[0] for c in seen_coords])
        lons = np.array([c[1] for c in seen_coords])
        dists = haversine_m(row["latitude"], row["longitude"], lats, lons)
        if dists.min() > OVERLAP_RADIUS_M:
            kept.append(i)
            seen_coords.append((row["latitude"], row["longitude"]))

    google_deduped = google_filtered.loc[kept].copy().reset_index(drop=True)
    print(f"Google setelah dedup internal (radius {OVERLAP_RADIUS_M}m): {len(google_deduped)}")

    # Cari Google venue yang tidak overlap dengan existing
    exist_lat = existing["latitude"].to_numpy()
    exist_lon = existing["longitude"].to_numpy()

    new_venues = []
    for _, row in google_deduped.iterrows():
        dists = haversine_m(row["latitude"], row["longitude"], exist_lat, exist_lon)
        if dists.min() > OVERLAP_RADIUS_M:
            new_venues.append(row)

    if not new_venues:
        print("\nTidak ada venue Google baru yang belum ada di dataset existing.")
        return

    google_new = pd.DataFrame(new_venues).reset_index(drop=True)
    print(f"Venue Google baru (tidak overlap existing): {len(google_new)}")
    print("\nDistribusi kategori venue baru:")
    print(google_new["venue_category"].value_counts().to_string())

    # Assign venue_id baru
    google_new["venue_id"] = [f"google_{i:05d}" for i in range(len(google_new))]

    # Pastikan kolom sesuai existing (isi kolom yang tidak ada dengan default)
    DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    day_cols = [f"{d}_buka" for d in DAYS_ID] + [f"{d}_tutup" for d in DAYS_ID]

    # Kolom tambahan yang ada di existing tapi mungkin tidak di Google new
    for col in ["checkin_count", "last_checkin", "osm_url", "References"]:
        if col not in google_new.columns:
            google_new[col] = None
    google_new["checkin_count"] = google_new.get("checkin_count", pd.Series([0] * len(google_new)))
    if "hours_source" not in google_new.columns:
        google_new["hours_source"] = "google_places"
    if "data_collected" not in google_new.columns:
        google_new["data_collected"] = date.today().strftime("%Y-%m-%d")

    # Reindex kolom sesuai existing
    for col in existing.columns:
        if col not in google_new.columns:
            google_new[col] = None

    google_new = google_new[existing.columns]

    # Gabung
    combined = pd.concat([existing, google_new], ignore_index=True)
    n_final = len(combined)
    print(f"\nDataset final setelah merge Google venues: {n_final}")
    print(f"  Existing: {n_existing}")
    print(f"  Tambahan dari Google: {len(google_new)}")

    combined.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
    print(f"Tersimpan -> {config.MERGED_VENUES_ENRICHED_CSV}")

    print("\nDistribusi kategori final:")
    print(combined["venue_category"].value_counts().to_string())


if __name__ == "__main__":
    main()

"""
Isi jam buka default untuk venue yang Google Places tidak return regularOpeningHours
(semua hari = Tutup). Terjadi pada venue outdoor, monumen, pantai, wahana dalam
theme park — Google tidak selalu punya data jam untuk tipe venue ini.

Default per kategori (berdasarkan pengetahuan umum + spot-check Google Maps):
- Monument / Landmark  : 00:00-23:59 (outdoor, buka 24 jam)
- Beach                : 00:00-23:59 (outdoor, buka 24 jam)
- Historic Site        : 08:00-17:00
- Temple               : 06:00-18:00
- Theme Park Ride/Att  : 10:00-18:00 (ikut jam theme park induk)
- Theme Park           : 10:00-20:00
- Zoo                  : 08:00-17:00
- Museum               : 08:00-16:00
- History Museum       : 08:00-16:00
- Art Museum           : 09:00-17:00
- Science Museum       : 08:00-16:00
- Aquarium             : 09:00-17:00

hours_source diset ke 'default_category' agar bisa dibedakan dari 'google_places'.

Input/Output: data/processed/merged_venues_enriched.csv (in-place)
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

DEFAULT_HOURS = {
    "Monument / Landmark":        ("00:00", "23:59"),
    "Beach":                      ("00:00", "23:59"),
    "Historic Site":              ("08:00", "17:00"),
    "Temple":                     ("06:00", "18:00"),
    "Buddhist Temple":            ("06:00", "18:00"),
    "Theme Park Ride / Attraction": ("10:00", "18:00"),
    "Theme Park":                 ("10:00", "20:00"),
    "Zoo":                        ("08:00", "17:00"),
    "Museum":                     ("08:00", "16:00"),
    "History Museum":             ("08:00", "16:00"),
    "Art Museum":                 ("09:00", "17:00"),
    "Science Museum":             ("08:00", "16:00"),
    "Aquarium":                   ("09:00", "17:00"),
}


def main():
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    buka_cols = [f"{d}_buka" for d in DAYS_ID]

    # Catch 2 kasus:
    # 1. Semua hari Tutup
    # 2. Mayoritas hari Tutup (>=5) — bug cache Google: 1-2 hari ada data tapi sisanya kosong
    n_tutup_per_row = (df[buka_cols] == "Tutup").sum(axis=1)
    mask_all_tutup = n_tutup_per_row >= 5
    n_before = mask_all_tutup.sum()
    print(f"Venue >=5 hari Tutup (sebelum): {n_before}")

    n_filled = 0
    for idx in df[mask_all_tutup].index:
        cat = df.at[idx, "venue_category"]
        if cat not in DEFAULT_HOURS:
            continue
        buka, tutup = DEFAULT_HOURS[cat]
        for day in DAYS_ID:
            df.at[idx, f"{day}_buka"] = buka
            df.at[idx, f"{day}_tutup"] = tutup
        df.at[idx, "hours_source"] = "default_category"
        n_filled += 1

    mask_still_tutup = (df[buka_cols] == "Tutup").sum(axis=1) >= 5
    n_after = mask_still_tutup.sum()

    print(f"Diisi default per kategori: {n_filled}")
    print(f"Venue >=5 hari Tutup (sesudah): {n_after}")
    if n_after > 0:
        print("Masih Tutup (kategori tidak ada di DEFAULT_HOURS):")
        print(df[mask_still_tutup][["name", "venue_category"]].to_string())

    df.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
    print(f"\nTersimpan -> {config.MERGED_VENUES_ENRICHED_CSV}")

    print("\nDistribusi hours_source final:")
    print(df["hours_source"].value_counts().to_string())


if __name__ == "__main__":
    main()

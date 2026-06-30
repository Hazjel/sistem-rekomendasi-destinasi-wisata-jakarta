"""
Cleaning post-merge + post-enrich: buang venue yang lolos filter sebelumnya
tapi terdeteksi noise saat spot-check manual di merged_venues_enriched.csv.

Kasus noise yang ditangani:
- Kantor pemerintah (BPKP, dll)
- Venue luar Jakarta (Keraton Solo, Klenteng Semarang, Prambanan, dll)
- Bukan destinasi wisata (salon, kolam renang hotel, nama jalan, rumah sakit)
- Nama ambigu / tidak dikenal sebagai destinasi wisata Jakarta

Input:  data/processed/merged_venues_enriched.csv
Output: data/processed/merged_venues_enriched.csv (in-place, overwrite)
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import config
from dki_boundary import load_dki_polygon, is_in_dki


def main():
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    n_before = len(df)
    print(f"Venue sebelum cleaning post-merge: {n_before}")

    blacklist_lower = {b.lower() for b in config.STEPS_NAME_BLACKLIST}
    name_lower = df["name"].str.lower().fillna("")

    mask_blacklist = name_lower.isin(blacklist_lower)
    removed = df.loc[mask_blacklist, "name"].tolist()

    # Filter koordinat: buang venue di luar polygon administratif DKI Jakarta
    dki_poly = load_dki_polygon()
    mask_outside = ~df.apply(
        lambda r: is_in_dki(r["latitude"], r["longitude"], dki_poly), axis=1
    )
    outside_names = df.loc[mask_outside & ~mask_blacklist, "name"].tolist()

    # Filter venue tutup permanen/sementara (dari businessStatus Google Places)
    CLOSED_STATUSES = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}
    mask_closed = df["business_status"].isin(CLOSED_STATUSES)
    closed_names = df.loc[mask_closed & ~mask_blacklist & ~mask_outside, "name"].tolist()

    mask_drop = mask_blacklist | mask_outside | mask_closed
    df_clean = df[~mask_drop].copy().reset_index(drop=True)
    n_after = len(df_clean)

    print(f"Dibuang (blacklist): {mask_blacklist.sum()}")
    if removed:
        print("  Daftar yang dibuang:")
        for name in removed:
            print(f"    - {name}")
    print(f"Dibuang (luar polygon DKI): {mask_outside.sum()}")
    if outside_names:
        for name in outside_names:
            print(f"    - {name}")
    print(f"Dibuang (closed/tutup permanen atau sementara): {mask_closed.sum()}")
    if closed_names:
        for name in closed_names:
            status = df.loc[df["name"] == name, "business_status"].values[0]
            print(f"    - [{status}] {name}")
    print(f"Venue setelah cleaning: {n_after}")

    tmp = config.MERGED_VENUES_ENRICHED_CSV + ".tmp"
    df_clean.to_csv(tmp, index=False)
    os.replace(tmp, config.MERGED_VENUES_ENRICHED_CSV)
    print(f"\nTersimpan -> {config.MERGED_VENUES_ENRICHED_CSV}")


if __name__ == "__main__":
    main()

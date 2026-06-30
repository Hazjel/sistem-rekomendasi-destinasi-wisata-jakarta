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
import config


def main():
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    n_before = len(df)
    print(f"Venue sebelum cleaning post-merge: {n_before}")

    blacklist_lower = {b.lower() for b in config.STEPS_NAME_BLACKLIST}
    name_lower = df["name"].str.lower().fillna("")

    mask_blacklist = name_lower.isin(blacklist_lower)
    removed = df.loc[mask_blacklist, "name"].tolist()

    df_clean = df[~mask_blacklist].copy().reset_index(drop=True)
    n_after = len(df_clean)

    print(f"Dibuang (blacklist): {mask_blacklist.sum()}")
    if removed:
        print("  Daftar yang dibuang:")
        for name in removed:
            print(f"    - {name}")
    print(f"Venue setelah cleaning: {n_after}")

    df_clean.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
    print(f"\nTersimpan -> {config.MERGED_VENUES_ENRICHED_CSV}")


if __name__ == "__main__":
    main()

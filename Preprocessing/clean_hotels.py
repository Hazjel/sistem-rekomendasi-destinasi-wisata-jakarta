"""
Bersihkan hotels_google.csv: buang kost, rusunawa, asrama, coliving,
venue luar DKI Jakarta daratan, dan noise non-penginapan.

Input:  data/processed/hotels_google.csv
Output: data/processed/jakarta_hotels.csv
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import config
from dki_boundary import load_dki_polygon, is_in_dki

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOTELS_CLEAN_CSV = config.HOTELS_CSV

# Kata kunci nama yang menunjukkan bukan hotel wisatawan
NOISE_KEYWORDS = [
    "kost", "kos ", "kos-", "rusun", "asrama", "coliving", "co-living",
    "co living", "penginapan dan kost", "syariah grand sakinah",
    "rumah kost", "rumah sewa", "gang online", "perumahan", "apartemen",
    "residence", "residences", "suites", # terlalu banyak false positive, cek lebih lanjut
]

# Nama persis yang jelas noise
NOISE_EXACT = {
    "gang online",
    "kost terdekat",
    "poins mall",
    "pantai cikaya",
    "pulau gusung belut",
    "eko lingkis",
    "bscmp baronang ekolingkis",
    "pantai indah dafap",
    "rumah mamah izzan",
    "tudinpetot",
    "rumah ungu",
    "lagoa sinar",
    "ende elok",
    "dinar family",
    "permai hotel",  # cek dulu
    "cikunir",
    "kost mahesa",
    "hubert's kost",
    "rumah kost 28d",
    "kos loving hut",
    "garuda residence sa'aba 43 kost",
    "patra tomang residence (executive kost at tanjung duren)",
    "cove aora meruya - kost",
    "beranda istirahat meruya",
    "rusunawa penggilingan tower c",
    "rusun marunda cluster b",
    "rusun cinta kasih tzu chi",
    "asrama haji pondok gede (gedung a)",
    "upt asrama haji embarkasi jakarta",
    "flet perwira asrama polisi airud",
    "wisma indonesia",
    "wisma nurani 2",
    "wisma novita hj.amang buaran",
    "perum jatinegara baru",
    "samesta east point apartment",
    "apartemen sentra timur",
    "apartemen kedoya elok",
    "apartemen puri park view",
    "akr gallery west apartment",
    "bassura city apartement by toptravel",
    "malale residence",
    "graha mutiara minimalis 2",
    "perumahan buana gardenia blok b-3",
    "golf lake residence, cluster victoria hills 2",
    "ardinan residence jaticempaka",
    "the segaran house (syariah)",
    "rumah kost 122",
    "rumah kost 123",
    "micasa suites (kost & co-living)",
    "cove t63 - coliving tomang",
    "cove veranda - coliving cipayung",
    "cove bening boutique - coliving pondok gede",
    "rukita iconic kelapa gading - kost coliving",
    "urbanview greenville jakarta",
    "bale puri",
    "midtown residence",
    "hobihobi [pondok wisata]",
    "melrose place residence",
    "icon residence",
    "d'paragon kebon jeruk jakarta",
    "d'paragon menteng jakarta",
    "padina soho and residence",
    "veranda serviced residence puri",
    "casablanca east residence",
    "namroom at kalimalang",
    "puribanda townhouse",
    "cabin hotel",   # terlihat seperti kost
}

# Google types yang menunjukkan bukan hotel wisatawan
NOISE_TYPES = {"apartment", "real_estate_agency", "condominium_complex"}


def main():
    df = pd.read_csv(HOTELS_CLEAN_CSV if os.path.exists(HOTELS_CLEAN_CSV)
                     else "data/processed/hotels_google.csv")
    # Selalu baca dari raw
    df = pd.read_csv("data/processed/hotels_google.csv")
    print(f"Hotel raw: {len(df)}")

    name_lower = df["name"].str.lower().str.strip()

    # 1. Filter polygon DKI Jakarta daratan (exclude Kepulauan Seribu)
    dki_poly = load_dki_polygon()
    mask_in_dki = df.apply(
        lambda r: is_in_dki(r["latitude"], r["longitude"], dki_poly), axis=1
    )
    n_out = (~mask_in_dki).sum()
    print(f"Buang luar DKI: {n_out}")
    for n in df[~mask_in_dki]["name"]:
        print(f"  - {n}")
    df = df[mask_in_dki].copy()
    name_lower = df["name"].str.lower().str.strip()

    # 2. Filter nama exact noise
    mask_exact = name_lower.isin(NOISE_EXACT)
    print(f"\nBuang noise (nama exact): {mask_exact.sum()}")
    for n in df[mask_exact]["name"]:
        print(f"  - {n}")
    df = df[~mask_exact].copy()
    name_lower = df["name"].str.lower().str.strip()

    # 3. Filter nama mengandung keyword kost/rusun/asrama
    KOST_KEYWORDS = [
        "kost", " kos ", "-kos-", "rusun", "asrama haji",
        "penginapan dan kost", "rumah kost", "rumah sewa barat",
    ]
    mask_kost = name_lower.apply(
        lambda n: any(kw in n for kw in KOST_KEYWORDS)
    )
    print(f"\nBuang kost/rusun/asrama: {mask_kost.sum()}")
    for n in df[mask_kost]["name"]:
        print(f"  - {n}")
    df = df[~mask_kost].copy()
    name_lower = df["name"].str.lower().str.strip()

    # 4. Filter google_types mengandung apartment/real_estate
    if "google_types" in df.columns:
        mask_apt = df["google_types"].fillna("").str.lower().apply(
            lambda t: any(nt in t for nt in NOISE_TYPES)
        ) & ~name_lower.str.contains("hotel|inn|hostel|motel", na=False)
        print(f"\nBuang apartment/real_estate (bukan hotel): {mask_apt.sum()}")
        for n in df[mask_apt]["name"]:
            print(f"  - {n}")
        df = df[~mask_apt].copy()

    # 4b. Filter koordinat daratan Jakarta (exclude Kepulauan Seribu lat < -6.05)
    mask_kepulauan = df["latitude"] > -6.05
    print(f"\nBuang Kepulauan Seribu (lat > -6.05): {mask_kepulauan.sum()}")
    for n in df[mask_kepulauan]["name"]:
        print(f"  - {n}")
    df = df[~mask_kepulauan].copy()
    name_lower = df["name"].str.lower().str.strip()

    # 4c. Buang "residence" yang bukan hotel (kost/apartemen terselubung)
    RESIDENCE_NOISE = {
        "harlys residence",
        "super oyo 591 mn residence syariah",
    }
    mask_res = name_lower.isin(RESIDENCE_NOISE)
    print(f"\nBuang residence noise: {mask_res.sum()}")
    for n in df[mask_res]["name"]:
        print(f"  - {n}")
    df = df[~mask_res].copy()
    name_lower = df["name"].str.lower().str.strip()

    # 5. Filter rating < 3.0 (sangat buruk) atau rating_count < 10 (tidak signifikan)
    mask_low = (
        (df["google_rating"].fillna(5) < 3.0) |
        (df["google_rating_count"].fillna(100) < 10)
    )
    print(f"\nBuang rating buruk/count rendah (<3.0 atau <10 review): {mask_low.sum()}")
    for n in df[mask_low]["name"]:
        print(f"  - {n}")
    df = df[~mask_low].copy()

    print(f"\nHotel bersih: {len(df)}")
    df.to_csv(HOTELS_CLEAN_CSV, index=False)
    print(f"Tersimpan -> {HOTELS_CLEAN_CSV}")

    # Summary
    print(f"\nSample hotel yang tersisa:")
    print(df[["name", "google_rating", "google_rating_count"]].head(20).to_string())


if __name__ == "__main__":
    main()

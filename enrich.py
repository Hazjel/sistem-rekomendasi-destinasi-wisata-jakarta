"""
Lengkapi venue mentah:
    - Jam buka/tutup per hari ({Hari}_buka, {Hari}_tutup) -> dari tag OSM
      `opening_hours` (DATA NYATA). Kosong = "Tutup". Jika tag tidak ada,
      pakai default per kategori (ditandai hours_source=default).
    - unique_visitors, References, time_spent -> SIMULASI sintetis
      (metrik traffic privat, tak tersedia di API publik).

Output: data/venues_enriched.csv
"""
import numpy as np
import pandas as pd

import config
from openhours import DAYS_ID, parse_opening_hours

# Profil per prefix kategori: (rata2 rating count basis, menit time_spent).
CATEGORY_PROFILE = {
    "tourism:theme_park": (4000, 240),
    "tourism:zoo":        (3000, 180),
    "tourism:aquarium":   (2500, 150),
    "tourism:museum":     (1200, 90),
    "tourism:gallery":    (600, 70),
    "tourism:attraction": (1500, 80),
    "tourism:viewpoint":  (800, 40),
    "leisure:park":       (2000, 60),
    "leisure:garden":     (700, 50),
    "historic":           (900, 45),
    "amenity:place_of_worship": (1000, 40),
    "amenity:marketplace":      (2500, 70),
}

# Jam default per prefix kategori bila opening_hours OSM kosong.
# tuple (buka, tutup) untuk hari aktif; daftar hari libur (index 0=Senin).
# format: {"hours": (buka,tutup), "closed": [idx hari tutup]}
DEFAULT_HOURS = {
    "tourism:museum":   {"hours": ("09:00", "16:00"), "closed": [0]},   # museum tutup Senin
    "tourism:gallery":  {"hours": ("10:00", "18:00"), "closed": [0]},
    "tourism:theme_park": {"hours": ("09:00", "18:00"), "closed": []},
    "tourism:zoo":      {"hours": ("08:00", "17:00"), "closed": []},
    "tourism:aquarium": {"hours": ("09:00", "20:00"), "closed": []},
    "leisure:park":     {"hours": ("06:00", "18:00"), "closed": []},
    "leisure:garden":   {"hours": ("06:00", "18:00"), "closed": []},
    "amenity:place_of_worship": {"hours": ("00:00", "24:00"), "closed": []},
    "amenity:marketplace": {"hours": ("06:00", "20:00"), "closed": []},
}
DEFAULT_FALLBACK = {"hours": ("09:00", "17:00"), "closed": []}


def profile_for(category):
    if category in CATEGORY_PROFILE:
        return CATEGORY_PROFILE[category]
    prefix = category.split(":")[0]
    for key, val in CATEGORY_PROFILE.items():
        if key.split(":")[0] == prefix:
            return val
    return (800, 60)


def default_hours_for(category):
    if category in DEFAULT_HOURS:
        return DEFAULT_HOURS[category]
    prefix = category.split(":")[0]
    for key, val in DEFAULT_HOURS.items():
        if key.split(":")[0] == prefix:
            return val
    return DEFAULT_FALLBACK


def hours_row(raw_oh, category):
    """Kembalikan (dict {Hari: (buka,tutup)|None}, source)."""
    parsed = parse_opening_hours(raw_oh)
    if any(v is not None for v in parsed.values()):
        return parsed, "osm"
    # fallback default per kategori.
    cfg = default_hours_for(category)
    out = {}
    for i, day in enumerate(DAYS_ID):
        out[day] = None if i in cfg["closed"] else cfg["hours"]
    return out, "default"


def build_reference(row):
    """Link sumber/referensi venue: website > wikipedia > wikidata > maps."""
    web = str(row.get("website", "") or "")
    if web:
        return web
    wp = str(row.get("wikipedia", "") or "")
    if wp and ":" in wp:
        lang, title = wp.split(":", 1)
        return f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
    wd = str(row.get("wikidata", "") or "")
    if wd:
        return f"https://www.wikidata.org/wiki/{wd}"
    return str(row.get("maps_url", "") or "")


def main():
    rng = np.random.default_rng(config.RANDOM_SEED)
    fill = {c: "" for c in ["opening_hours", "website", "wikipedia",
                            "wikidata", "osm_url", "maps_url"]}
    df = pd.read_csv(config.RAW_CSV).fillna(fill)

    visitors, refs, spent, sources = [], [], [], []
    day_cols = {f"{d}_buka": [] for d in DAYS_ID}
    day_cols.update({f"{d}_tutup": [] for d in DAYS_ID})

    for _, row in df.iterrows():
        cat = row["venue_category"]
        # --- jam buka/tutup (nyata > default) ---
        hours, source = hours_row(row["opening_hours"], cat)
        sources.append(source)
        for d in DAYS_ID:
            hv = hours[d]
            day_cols[f"{d}_buka"].append(hv[0] if hv else "Tutup")
            day_cols[f"{d}_tutup"].append(hv[1] if hv else "Tutup")

        # --- References = link sumber (data nyata dari tag OSM) ---
        refs.append(build_reference(row))

        # --- metrik popularitas sintetis ---
        base, minutes = profile_for(cat)
        scale = rng.lognormal(mean=0.0, sigma=0.5)
        n_ref = max(int(base * scale * rng.uniform(0.02, 0.05)), 1)
        # unique_visitors diturunkan dari popularitas sintetis (rater 2-5%).
        visitors.append(int(n_ref / rng.uniform(0.02, 0.05)))
        spent.append(round(minutes * rng.uniform(0.8, 1.2), 1))

    df["unique_visitors"] = visitors
    for col, vals in day_cols.items():
        df[col] = vals
    df["References"] = refs
    df["time_spent"] = spent
    df["hours_source"] = sources

    day_order = []
    for d in DAYS_ID:
        day_order += [f"{d}_buka", f"{d}_tutup"]
    cols = (["venue_id", "name", "venue_category", "latitude", "longitude",
             "unique_visitors"] + day_order
            + ["References", "time_spent", "hours_source",
               "osm_url", "maps_url"])
    df[cols].to_csv(config.ENRICHED_CSV, index=False)

    n_osm = sources.count("osm")
    print(f"Enriched {len(df)} venue -> {config.ENRICHED_CSV}")
    print(f"  jam dari OSM nyata: {n_osm} | default: {len(df) - n_osm}")


if __name__ == "__main__":
    main()

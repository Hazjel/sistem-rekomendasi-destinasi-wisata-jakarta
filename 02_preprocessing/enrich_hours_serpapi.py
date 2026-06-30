"""
Enrich jam buka per hari via SerpAPI Google Maps.

Pakai 1 kredit per venue. Free plan = 249 kredit -> prioritaskan venue
dengan checkin_count tertinggi (paling populer, paling penting akurat).

Format jam Google Maps: "8 AM-9 PM" -> diparse ke "08:00"/"21:00".

Input:  data/processed/merged_venues.csv
Output: data/processed/merged_venues_enriched.csv
Cache:  data/processed/serpapi_cache/ (1 json per venue, hindari re-query)

Set SERPAPI_KEY sebagai env var sebelum jalankan:
  Windows: set SERPAPI_KEY=your_key_here
"""
import json
import os
import re
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

CACHE_DIR = "data/processed/serpapi_cache"
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
DAY_EN_TO_ID = {
    "monday": "Senin", "tuesday": "Selasa", "wednesday": "Rabu",
    "thursday": "Kamis", "friday": "Jumat", "saturday": "Sabtu", "sunday": "Minggu"
}


def parse_time(t):
    """'8 AM' -> '08:00', '9 PM' -> '21:00'."""
    t = t.strip()
    m = re.match(r"(\d+)(?::(\d+))?\s*(AM|PM)", t, re.IGNORECASE)
    if not m:
        return None
    h, mins, period = int(m.group(1)), int(m.group(2) or 0), m.group(3).upper()
    if period == "PM" and h != 12:
        h += 12
    elif period == "AM" and h == 12:
        h = 0
    return f"{h:02d}:{mins:02d}"


def parse_hours(hours_list):
    """[{'monday': '8 AM-9 PM'}, ...] -> dict {Hari: (buka, tutup) | None}."""
    result = {d: None for d in DAYS_ID}
    for entry in hours_list:
        for day_en, val in entry.items():
            day_id = DAY_EN_TO_ID.get(day_en.lower())
            if not day_id:
                continue
            if val.lower() in ("closed", "tutup"):
                result[day_id] = None
                continue
            if "open 24 hours" in val.lower():
                result[day_id] = ("00:00", "23:59")
                continue
                continue
            parts = re.split(r"[–\-]", val, maxsplit=1)
            if len(parts) == 2:
                buka = parse_time(parts[0])
                tutup = parse_time(parts[1])
                if buka and tutup:
                    result[day_id] = (buka, tutup)
    return result


def fetch_hours(name, lat, lon, api_key, venue_idx):
    cache_path = os.path.join(CACHE_DIR, f"{venue_idx}.json")
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f), True

    params = {
        "api_key": api_key,
        "engine": "google_maps",
        "q": f"{name} Jakarta",
        "ll": f"@{lat},{lon},15z",
        "type": "search",
    }
    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=20)
        data = r.json()
        hours_raw = data.get("place_results", {}).get("hours")
        result = hours_raw if hours_raw else None
    except Exception:
        result = None

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f)
    return result, False


def main():
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        raise RuntimeError("Set env var SERPAPI_KEY terlebih dahulu.")

    os.makedirs(CACHE_DIR, exist_ok=True)

    df = pd.read_csv(config.MERGED_VENUES_CSV)
    print(f"Total venue: {len(df)}")

    # Prioritas: checkin_count tertinggi, max 249 venue (sisa kredit)
    df_sorted = df.sort_values("checkin_count", ascending=False).reset_index(drop=True)
    MAX_REQUESTS = 249
    to_process = df_sorted.head(MAX_REQUESTS).copy()
    print(f"Diproses: {len(to_process)} venue (tertinggi by checkin_count)")
    print(f"Sisa {len(df) - len(to_process)} venue tetap pakai jam OSM/default")

    n_ok, n_miss, n_cached = 0, 0, 0

    for i, (_, row) in enumerate(to_process.iterrows()):
        hours_raw, cached = fetch_hours(
            row["name"], row["latitude"], row["longitude"], api_key, int(row["venue_id"])
        )

        if cached:
            n_cached += 1
        elif hours_raw:
            n_ok += 1
            time.sleep(1.2)  # ~50 req/menit max free tier
        else:
            n_miss += 1
            time.sleep(1.2)

        if hours_raw:
            parsed = parse_hours(hours_raw)
            for day in DAYS_ID:
                val = parsed.get(day)
                orig_idx = df_sorted.index[i]
                df.at[orig_idx, f"{day}_buka"] = val[0] if val else "Tutup"
                df.at[orig_idx, f"{day}_tutup"] = val[1] if val else "Tutup"
            df.at[df_sorted.index[i], "hours_source"] = "google_maps"

        if (i + 1) % 25 == 0:
            df.to_csv("data/processed/merged_venues_enriched.csv", index=False)
            print(f"  {i+1}/{len(to_process)} | ok:{n_ok} miss:{n_miss} cache:{n_cached} (auto-saved)")

    out = "data/processed/merged_venues_enriched.csv"
    df.to_csv(out, index=False)

    print(f"\nSelesai")
    print(f"  Google Maps sukses: {n_ok + n_cached}")
    print(f"  Tidak ditemukan: {n_miss}")
    print(f"\nDistribusi hours_source:")
    print(df["hours_source"].value_counts().to_string())
    print(f"\nTersimpan -> {out}")


if __name__ == "__main__":
    main()

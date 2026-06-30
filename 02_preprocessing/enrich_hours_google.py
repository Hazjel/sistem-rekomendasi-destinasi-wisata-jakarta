"""
Enrich jam buka per hari via Google Places API (New).

Lebih akurat dari SerpAPI (sumber langsung Google Maps) dan cover lebih banyak
venue. Pakai Text Search untuk cari place_id, lalu Place Details untuk jam buka.

Cost: ~$0.017/venue (Text Search $0.005 + Place Details $0.012) -> 281 venue ~$4.8
      Jauh di bawah kredit trial Google Cloud ($300 equivalent).

Set env var GOOGLE_PLACES_KEY sebelum jalankan:
  Windows: set GOOGLE_PLACES_KEY=your_key

Input:  data/processed/merged_venues.csv
Output: data/processed/merged_venues_enriched.csv
Cache:  data/processed/google_cache/ (json per venue_id, hindari re-query)
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

CACHE_DIR = "data/processed/google_cache"
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
# Google: 0=Sunday, 1=Monday, ..., 6=Saturday
GDAY_TO_ID = {0: "Minggu", 1: "Senin", 2: "Selasa", 3: "Rabu",
              4: "Kamis", 5: "Jumat", 6: "Sabtu"}

# Fallback jam per kategori untuk venue yang Google tidak punya data jam
# (outdoor, monumen, pantai) atau return data parsial (<2 hari terisi).
DEFAULT_HOURS = {
    "Monument / Landmark":          ("00:00", "23:59"),
    "Beach":                        ("00:00", "23:59"),
    "Historic Site":                ("08:00", "17:00"),
    "Temple":                       ("06:00", "18:00"),
    "Buddhist Temple":              ("06:00", "18:00"),
    "Theme Park Ride / Attraction": ("10:00", "18:00"),
    "Theme Park":                   ("10:00", "20:00"),
    "Zoo":                          ("08:00", "17:00"),
    "Museum":                       ("08:00", "16:00"),
    "History Museum":               ("08:00", "16:00"),
    "Art Museum":                   ("09:00", "17:00"),
    "Science Museum":               ("08:00", "16:00"),
    "Aquarium":                     ("09:00", "17:00"),
}


def apply_default_hours(df, idx):
    """Isi jam default per kategori jika Google tidak punya data jam."""
    cat = df.at[idx, "venue_category"]
    if cat not in DEFAULT_HOURS:
        return
    buka, tutup = DEFAULT_HOURS[cat]
    for day in DAYS_ID:
        df.at[idx, f"{day}_buka"] = buka
        df.at[idx, f"{day}_tutup"] = tutup
    df.at[idx, "hours_source"] = "default_category"
BASE = "https://places.googleapis.com/v1"


def search_place_id(name, lat, lon, api_key):
    """Text Search -> dapat place_id."""
    url = f"{BASE}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName",
    }
    body = {
        "textQuery": f"{name} Jakarta",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": 500.0
            }
        },
        "maxResultCount": 1,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        if r.status_code != 200:
            return None
        places = r.json().get("places", [])
        return places[0]["id"] if places else None
    except Exception:
        return None


def get_place_details(place_id, api_key):
    """Place Details -> jam buka + rating + deskripsi + dll. Return dict atau None."""
    url = f"{BASE}/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join([
            "regularOpeningHours",
            "rating",
            "userRatingCount",
            "priceLevel",
            "editorialSummary",
            "types",
            "websiteUri",
            "goodForChildren",
            "nationalPhoneNumber",
        ]),
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()

        # Parse jam buka
        periods = data.get("regularOpeningHours", {}).get("periods", [])
        hours = {d: None for d in DAYS_ID}
        for p in periods:
            day_num = p.get("open", {}).get("day")
            day_id = GDAY_TO_ID.get(day_num)
            if not day_id:
                continue
            o, c = p.get("open", {}), p.get("close", {})
            oh, om = o.get("hour", 0), o.get("minute", 0)
            ch, cm = c.get("hour", 0), c.get("minute", 0)
            hours[day_id] = (f"{oh:02d}:{om:02d}", f"{ch:02d}:{cm:02d}")

        return {
            "hours": hours,
            "rating": data.get("rating"),
            "user_rating_count": data.get("userRatingCount"),
            "price_level": data.get("priceLevel"),
            "description": data.get("editorialSummary", {}).get("text"),
            "types": data.get("types", []),
            "website": data.get("websiteUri"),
            "phone": data.get("nationalPhoneNumber"),
            "good_for_children": data.get("goodForChildren"),
        }
    except Exception:
        return None


def main():
    api_key = os.environ.get("GOOGLE_PLACES_KEY", "")
    if not api_key:
        raise RuntimeError("Set env var GOOGLE_PLACES_KEY terlebih dahulu.")

    os.makedirs(CACHE_DIR, exist_ok=True)
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV
                     if os.path.exists(config.MERGED_VENUES_ENRICHED_CSV)
                     else config.MERGED_VENUES_CSV)
    print(f"Total venue: {len(df)}")

    n_ok, n_miss, n_cached = 0, 0, 0

    for i, (idx, row) in enumerate(df.iterrows()):
        cache_path = os.path.join(CACHE_DIR, f"{str(row['venue_id']).replace('/', '_')}.json")

        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                details = json.load(f)
            n_cached += 1
        else:
            place_id = search_place_id(row["name"], row["latitude"],
                                        row["longitude"], api_key)
            time.sleep(0.3)
            details = get_place_details(place_id, api_key) if place_id else None
            time.sleep(0.3)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(details, f)
            if details:
                n_ok += 1
            else:
                n_miss += 1

        if details:
            hours = details.get("hours", {})
            filled_days = sum(1 for v in hours.values() if v is not None)
            for day in DAYS_ID:
                val = hours.get(day)
                df.at[idx, f"{day}_buka"] = val[0] if val else "Tutup"
                df.at[idx, f"{day}_tutup"] = val[1] if val else "Tutup"
            df.at[idx, "hours_source"] = "google_places"
            df.at[idx, "google_rating"] = details.get("rating")
            df.at[idx, "google_rating_count"] = details.get("user_rating_count")
            df.at[idx, "price_level"] = details.get("price_level")
            df.at[idx, "description"] = details.get("description")
            df.at[idx, "good_for_children"] = details.get("good_for_children")
            df.at[idx, "google_types"] = ",".join(details.get("types", []))
            if details.get("website") and not df.at[idx, "References"]:
                df.at[idx, "References"] = details.get("website")
            # Google kadang return response tapi jam parsial (< 2 hari terisi)
            # -> venue outdoor/monumen yang tidak punya jam formal di Google
            if filled_days < 2:
                apply_default_hours(df, idx)
        else:
            # Google tidak return data sama sekali -> fallback default kategori
            apply_default_hours(df, idx)

        if (i + 1) % 25 == 0:
            df.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
            print(f"  {i+1}/{len(df)} | ok:{n_ok} miss:{n_miss} cache:{n_cached} (saved)")

    out = config.MERGED_VENUES_ENRICHED_CSV
    df.to_csv(out, index=False)
    print(f"\nSelesai: {len(df)} venue")
    print(f"  Google Places sukses: {n_ok + n_cached}")
    print(f"  Tidak ditemukan: {n_miss}")
    print(f"\nDistribusi hours_source:")
    print(df["hours_source"].value_counts().to_string())
    print(f"\nTersimpan -> {out}")


if __name__ == "__main__":
    main()

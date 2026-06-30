"""
Kumpulkan hotel/penginapan Jakarta via Google Places API (New) Nearby Search.

Lebih akurat dari OSM: rating nyata, price level, selalu update.
Pakai koordinat pusat tiap zona cluster sebagai anchor search,
radius 5km per zona -> cover seluruh DKI Jakarta tanpa overlap besar.

Butuh env var GOOGLE_PLACES_KEY.

Output: data/processed/hotels_google.csv
Cache:  data/processed/google_hotel_cache/
"""
import json
import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

CACHE_DIR = "data/processed/google_hotel_cache"
BASE = "https://places.googleapis.com/v1"

# Titik anchor pencarian hotel -- pusat kota + tiap wilayah Jakarta
SEARCH_ANCHORS = [
    # Jakarta Pusat
    (-6.1754, 106.8272, "Menteng"),
    (-6.1600, 106.8450, "Kemayoran"),
    (-6.1950, 106.8200, "Tanah Abang"),
    # Jakarta Selatan
    (-6.2400, 106.7900, "Kebayoran Baru"),
    (-6.2600, 106.8100, "Mampang"),
    (-6.2900, 106.8300, "Pasar Minggu"),
    (-6.2200, 106.8700, "Pancoran"),
    (-6.3000, 106.7700, "Cilandak"),
    # Jakarta Utara
    (-6.1200, 106.8800, "Pademangan"),
    (-6.1000, 106.8500, "Penjaringan"),
    (-6.0900, 106.9200, "Cilincing"),
    (-6.1400, 106.7800, "Grogol Utara"),
    # Jakarta Barat
    (-6.1700, 106.7600, "Grogol"),
    (-6.2000, 106.7400, "Kebon Jeruk"),
    (-6.1500, 106.7200, "Cengkareng"),
    (-6.1900, 106.7000, "Kembangan"),
    # Jakarta Timur
    (-6.2100, 106.8900, "Jatinegara"),
    (-6.2500, 106.9200, "Kramat Jati"),
    (-6.1800, 106.9400, "Pulo Gadung"),
    (-6.2800, 106.8900, "Pasar Rebo"),
    # Kepulauan Seribu
    (-5.7200, 106.5700, "Kepulauan Seribu"),
]

DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
GDAY_TO_ID = {0: "Minggu", 1: "Senin", 2: "Selasa", 3: "Rabu",
              4: "Kamis", 5: "Jumat", 6: "Sabtu"}


def search_hotels_nearby(lat, lon, api_key, radius=5000):
    """Nearby Search kategori lodging. Return list place dicts."""
    url = f"{BASE}/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join([
            "places.id", "places.displayName", "places.formattedAddress",
            "places.location", "places.rating", "places.userRatingCount",
            "places.priceLevel", "places.regularOpeningHours",
            "places.websiteUri", "places.nationalPhoneNumber",
            "places.types", "places.editorialSummary",
        ]),
    }
    body = {
        "includedTypes": ["hotel", "lodging", "motel", "guest_house", "hostel"],
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": float(radius),
            }
        },
        "maxResultCount": 20,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=20)
        if r.status_code != 200:
            print(f"  Error {r.status_code}: {r.text[:100]}")
            return []
        return r.json().get("places", [])
    except Exception as e:
        print(f"  Exception: {e}")
        return []


def parse_hours(periods):
    result = {d: None for d in DAYS_ID}
    for p in periods:
        day_num = p.get("open", {}).get("day")
        day_id = GDAY_TO_ID.get(day_num)
        if not day_id:
            continue
        o, c = p.get("open", {}), p.get("close", {})
        oh, om = o.get("hour", 0), o.get("minute", 0)
        ch, cm = c.get("hour", 0), c.get("minute", 0)
        result[day_id] = (f"{oh:02d}:{om:02d}", f"{ch:02d}:{cm:02d}")
    return result


def main():
    api_key = os.environ.get("GOOGLE_PLACES_KEY", "")
    if not api_key:
        raise RuntimeError("Set env var GOOGLE_PLACES_KEY terlebih dahulu.")

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)

    all_hotels = {}  # place_id -> dict

    for lat, lon, area in SEARCH_ANCHORS:
        cache_path = os.path.join(CACHE_DIR, f"{area.replace(' ','_')}.json")
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                places = json.load(f)
            print(f"{area}: {len(places)} hotel (dari cache)")
        else:
            print(f"Search hotel: {area} ...")
            places = search_hotels_nearby(lat, lon, api_key)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(places, f, ensure_ascii=False)
            print(f"  {len(places)} hotel ditemukan")
            time.sleep(0.5)

        for p in places:
            pid = p.get("id")
            if pid and pid not in all_hotels:
                all_hotels[pid] = p

    print(f"\nTotal hotel unik: {len(all_hotels)}")

    rows = []
    for pid, p in all_hotels.items():
        loc = p.get("location", {})
        periods = p.get("regularOpeningHours", {}).get("periods", [])
        hours = parse_hours(periods)

        row = {
            "place_id": pid,
            "name": p.get("displayName", {}).get("text", ""),
            "address": p.get("formattedAddress", ""),
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "google_rating": p.get("rating"),
            "google_rating_count": p.get("userRatingCount"),
            "price_level": p.get("priceLevel"),
            "website": p.get("websiteUri", ""),
            "phone": p.get("nationalPhoneNumber", ""),
            "description": p.get("editorialSummary", {}).get("text", ""),
            "google_types": ",".join(p.get("types", [])),
        }
        for day in DAYS_ID:
            val = hours.get(day)
            row[f"{day}_buka"] = val[0] if val else "Tutup"
            row[f"{day}_tutup"] = val[1] if val else "Tutup"

        rows.append(row)

    df = pd.DataFrame(rows)

    # Filter kasar: pastikan dalam bounding box DKI Jakarta
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[(df["latitude"].between(-6.40, -5.10)) &
            (df["longitude"].between(106.50, 107.10))]

    out = "data/processed/hotels_google.csv"
    df.to_csv(out, index=False)

    print(f"\nHotel final: {len(df)}")
    print(f"Tersimpan -> {out}")
    if "google_rating" in df.columns:
        print(f"Rating: mean={df['google_rating'].mean():.2f}, "
              f"count={df['google_rating'].count()}")


if __name__ == "__main__":
    main()

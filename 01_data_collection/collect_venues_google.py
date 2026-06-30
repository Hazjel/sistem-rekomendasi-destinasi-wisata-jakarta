"""
Kumpulkan venue wisata Jakarta yang tidak ada di Massive-STEPS via Google Places
API (New) Nearby Search, per kategori dan per zona geografis.

Mengapa diperlukan:
- Massive-STEPS berbasis check-in Foursquare 2012-2018 -> cakupan tidak merata
- Venue terkenal seperti Kebun Binatang Ragunan, Ancol secara umum, dll
  mungkin tidak tercatat lengkap
- Google Places memberi data up-to-date: rating nyata, jam buka, deskripsi

Output: data/raw/venues_google_raw.csv
Cache:  data/raw/google_venues_cache/
Butuh env var GOOGLE_PLACES_KEY.
"""
import json
import os
import sys
import time
from datetime import date

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

CACHE_DIR = "data/raw/google_venues_cache"
BASE = "https://places.googleapis.com/v1"

# Pemetaan kategori Foursquare -> Google Places type
# Setiap entry: (foursquare_category, [google_types], label_pencarian)
CATEGORY_SEARCHES = [
    ("Zoo",              ["zoo"],                                          "Kebun Binatang"),
    ("Aquarium",         ["aquarium"],                                     "Akuarium"),
    ("Theme Park",       ["amusement_park", "water_park"],                "Taman Hiburan"),
    ("Museum",           ["museum"],                                       "Museum"),
    ("Art Museum",       ["art_gallery"],                                  "Galeri Seni"),
    ("Historic Site",    ["tourist_attraction", "cultural_landmark"],      "Situs Bersejarah"),
    ("History Museum",   ["history_museum"],                               "Museum Sejarah"),
    ("Science Museum",   ["museum"],                                        "Museum Sains"),
    ("Temple",           ["hindu_temple", "buddhist_temple"],              "Vihara/Pura"),
    ("Monument / Landmark", ["monument", "tourist_attraction"],            "Monumen"),
    ("Beach",            ["beach"],                                        "Pantai"),
    ("Theme Park Ride / Attraction", ["tourist_attraction", "amusement_park"], "Wahana Wisata"),
]

# Titik anchor pencarian -- sama dengan anchor hotel, cover seluruh DKI + Kepulauan Seribu
SEARCH_ANCHORS = [
    (-6.1754, 106.8272, "Menteng"),
    (-6.1600, 106.8450, "Kemayoran"),
    (-6.1950, 106.8200, "Tanah Abang"),
    (-6.2400, 106.7900, "Kebayoran Baru"),
    (-6.2600, 106.8100, "Mampang"),
    (-6.2900, 106.8300, "Pasar Minggu"),
    (-6.2200, 106.8700, "Pancoran"),
    (-6.3000, 106.7700, "Cilandak"),
    (-6.1200, 106.8800, "Pademangan"),
    (-6.1000, 106.8500, "Penjaringan"),
    (-6.0900, 106.9200, "Cilincing"),
    (-6.1400, 106.7800, "Grogol Utara"),
    (-6.1700, 106.7600, "Grogol"),
    (-6.2000, 106.7400, "Kebon Jeruk"),
    (-6.1500, 106.7200, "Cengkareng"),
    (-6.1900, 106.7000, "Kembangan"),
    (-6.2100, 106.8900, "Jatinegara"),
    (-6.2500, 106.9200, "Kramat Jati"),
    (-6.1800, 106.9400, "Pulo Gadung"),
    (-6.2800, 106.8900, "Pasar Rebo"),
    (-5.7200, 106.5700, "Kepulauan Seribu"),
]

DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
GDAY_TO_ID = {0: "Minggu", 1: "Senin", 2: "Selasa", 3: "Rabu",
              4: "Kamis", 5: "Jumat", 6: "Sabtu"}


def search_nearby(lat, lon, google_types, api_key, radius=5000):
    url = f"{BASE}/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join([
            "places.id", "places.displayName", "places.formattedAddress",
            "places.location", "places.rating", "places.userRatingCount",
            "places.priceLevel", "places.regularOpeningHours",
            "places.types", "places.editorialSummary",
            "places.goodForChildren", "places.nationalPhoneNumber",
        ]),
    }
    body = {
        "includedTypes": google_types,
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
            print(f"    Error {r.status_code}: {r.text[:100]}")
            return []
        return r.json().get("places", [])
    except Exception as e:
        print(f"    Exception: {e}")
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
    os.makedirs("data/raw", exist_ok=True)

    all_places = {}  # place_id -> (place_dict, foursquare_category)

    for fsq_cat, google_types, label in CATEGORY_SEARCHES:
        print(f"\n=== Kategori: {fsq_cat} ({label}) ===")
        cat_count = 0
        for lat, lon, area in SEARCH_ANCHORS:
            cache_key = f"{fsq_cat.replace('/', '_').replace(' ', '_')}_{area.replace(' ', '_')}"
            cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

            if os.path.exists(cache_path):
                with open(cache_path, encoding="utf-8") as f:
                    places = json.load(f)
            else:
                places = search_nearby(lat, lon, google_types, api_key)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(places, f, ensure_ascii=False)
                time.sleep(0.3)

            new_in_area = 0
            for p in places:
                pid = p.get("id")
                if pid and pid not in all_places:
                    all_places[pid] = (p, fsq_cat)
                    new_in_area += 1
            cat_count += new_in_area

        print(f"  Venue baru kategori ini: {cat_count}")

    print(f"\nTotal venue unik dari Google: {len(all_places)}")

    rows = []
    for pid, (p, fsq_cat) in all_places.items():
        loc = p.get("location", {})
        periods = p.get("regularOpeningHours", {}).get("periods", [])
        hours = parse_hours(periods)

        row = {
            "place_id": pid,
            "name": p.get("displayName", {}).get("text", ""),
            "venue_category": fsq_cat,
            "address": p.get("formattedAddress", ""),
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "google_rating": p.get("rating"),
            "google_rating_count": p.get("userRatingCount"),
            "price_level": p.get("priceLevel"),
            "description": p.get("editorialSummary", {}).get("text", ""),
            "good_for_children": p.get("goodForChildren"),
            "google_types": ",".join(p.get("types", [])),
            "phone": p.get("nationalPhoneNumber", ""),
            "hours_source": "google_places",
            "data_collected": date.today().strftime("%Y-%m-%d"),
        }
        for day in DAYS_ID:
            val = hours.get(day)
            row[f"{day}_buka"] = val[0] if val else "Tutup"
            row[f"{day}_tutup"] = val[1] if val else "Tutup"

        rows.append(row)

    df = pd.DataFrame(rows)

    # Filter bounding box DKI Jakarta
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[(df["latitude"].between(-6.40, -5.10)) &
            (df["longitude"].between(106.50, 107.10))]

    out = "data/raw/venues_google_raw.csv"
    df.to_csv(out, index=False)

    print(f"\nVenue final (dalam bbox DKI): {len(df)}")
    print(f"Tersimpan -> {out}")
    print(f"Rating: mean={df['google_rating'].mean():.2f}, "
          f"count={df['google_rating'].count()} venue punya rating")
    print("\nDistribusi kategori:")
    print(df["venue_category"].value_counts().to_string())


if __name__ == "__main__":
    main()

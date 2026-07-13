"""Tambah SATU venue baru via Google Places API -> data/raw/manual_venues.csv.

Search nama -> ambil place_id -> Details lengkap (koordinat, jam buka, rating,
kategori, foto, aksesibilitas). Kategori dipetakan ke skema dataset. Idempoten:
skip kalau venue_id sudah ada di manual_venues.csv.

Pakai:
  python src/preprocessing/add_venue_places.py "Perpustakaan Jakarta Nyi Ageng Serang" --venue-id manual_perpus_001
Butuh GOOGLE_PLACES_KEY di .env.
"""
import argparse
import os
import sys

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

load_dotenv()
KEY = os.environ.get("GOOGLE_PLACES_KEY", "")
BASE = "https://places.googleapis.com/v1"
MANUAL_CSV = "data/raw/manual_venues.csv"
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
GDAY_TO_ID = {1: "Senin", 2: "Selasa", 3: "Rabu", 4: "Kamis",
              5: "Jumat", 6: "Sabtu", 0: "Minggu"}

# Peta primaryType Google -> venue_category dataset. Perpustakaan -> kategori
# terdekat yang sudah ada; bila tak cocok, fallback 'General Entertainment'.
TYPE_MAP = {
    "library": "Library",
    "museum": "Museum", "art_gallery": "Art Gallery", "tourist_attraction": "Historic Site",
    "park": "Park", "place_of_worship": "Historic Site",
}


def search_place(name):
    url = f"{BASE}/places:searchText"
    headers = {"X-Goog-Api-Key": KEY,
               "X-Goog-FieldMask": "places.id,places.displayName,places.location"}
    body = {"textQuery": name,
            "locationBias": {"circle": {"center": {"latitude": -6.2, "longitude": 106.83},
                                        "radius": 40000}}}
    r = requests.post(url, headers=headers, json=body, timeout=15)
    r.raise_for_status()
    places = r.json().get("places", [])
    return places[0] if places else None


def get_details(place_id):
    url = f"{BASE}/places/{place_id}"
    headers = {"X-Goog-Api-Key": KEY, "X-Goog-FieldMask": ",".join([
        "displayName", "formattedAddress", "location",
        "regularOpeningHours", "currentOpeningHours",
        "rating", "userRatingCount", "priceLevel", "editorialSummary",
        "types", "primaryType", "websiteUri", "goodForChildren",
        "businessStatus", "accessibilityOptions", "parkingOptions",
        "paymentOptions", "restroom", "photos", "addressComponents"])}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def parse_hours(data):
    oh = data.get("regularOpeningHours") or data.get("currentOpeningHours") or {}
    periods = oh.get("periods", [])
    hours = {d: (None, None) for d in DAYS_ID}
    if periods and all("close" not in p for p in periods):
        return {d: ("00:00", "23:59") for d in DAYS_ID}
    for p in periods:
        did = GDAY_TO_ID.get(p.get("open", {}).get("day"))
        if not did:
            continue
        o, c = p.get("open", {}), p.get("close", {})
        hours[did] = (f"{o.get('hour',0):02d}:{o.get('minute',0):02d}",
                      f"{c.get('hour',0):02d}:{c.get('minute',0):02d}")
    return hours


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--venue-id", required=True)
    args = ap.parse_args()
    if not KEY:
        print("GOOGLE_PLACES_KEY kosong."); return

    place = search_place(args.name)
    if not place:
        print(f"Tak ketemu di Places: {args.name}"); return
    pid = place["id"]
    d = get_details(pid)
    loc = d.get("location", {})
    lat, lon = loc.get("latitude"), loc.get("longitude")
    hours = parse_hours(d)
    ptype = d.get("primaryType", "")
    category = TYPE_MAP.get(ptype, "General Entertainment")

    photos = d.get("photos", [])
    acc = d.get("accessibilityOptions", {}) or {}
    park = d.get("parkingOptions", {}) or {}
    pay = d.get("paymentOptions", {}) or {}
    subloc = locality = None
    for comp in d.get("addressComponents", []):
        t = comp.get("types", [])
        if "administrative_area_level_4" in t: subloc = comp.get("longText")
        elif "administrative_area_level_2" in t: locality = comp.get("longText")

    row = {
        "venue_id": args.venue_id,
        "name": d.get("displayName", {}).get("text", args.name),
        "venue_category": category,
        "latitude": lat, "longitude": lon,
        "address": d.get("formattedAddress"),
        "checkin_count": 0.0, "last_checkin": None, "osm_url": None,
        "References": None, "hours_source": "google_places",
    }
    for dd in DAYS_ID:
        row[f"{dd}_buka"], row[f"{dd}_tutup"] = hours[dd]
    row.update({
        "google_rating": d.get("rating"),
        "google_rating_count": d.get("userRatingCount"),
        "price_level": None, "description": d.get("editorialSummary", {}).get("text"),
        "good_for_children": d.get("goodForChildren"),
        "google_types": ",".join(d.get("types", [])),
        "primary_type": ptype, "business_status": d.get("businessStatus"),
        "wheelchair_accessible": acc.get("wheelchairAccessibleEntrance"),
        "has_parking": any(park.values()) if park else None,
        "accepts_cashless": pay.get("acceptsCashOnly") is False if pay else None,
        "has_restroom": d.get("restroom"),
        "photo_ref": photos[0].get("name") if photos else None,
        "sublocality": subloc, "locality": locality, "zone_id": None,
    })

    df = pd.read_csv(MANUAL_CSV) if os.path.exists(MANUAL_CSV) else pd.DataFrame()
    if not df.empty and args.venue_id in df["venue_id"].astype(str).values:
        print(f"[skip] {args.venue_id} sudah ada di {MANUAL_CSV}"); return
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(MANUAL_CSV, index=False)
    print(f"Ditambah: {row['name']} | kategori {category} | ({lat},{lon})")
    print(f"jam: {hours['Senin']}..{hours['Minggu']} | rating {row['google_rating']}")
    print(f"-> {MANUAL_CSV}. Lanjut: rebuild NB 02->03->04 (merge, cluster, time matrix).")


if __name__ == "__main__":
    main()

"""
Retry fetch Google Places untuk venue yang masih hours_source=default_category
dengan query alternatif (nama lebih pendek, tanpa tanda baca, + nama alternatif manual).
"""
import json
import os
import shutil
import sys
import time
import re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import config

BASE = "https://places.googleapis.com/v1"
CACHE_DIR = "data/processed/google_cache"
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
GDAY_TO_ID = {0: "Minggu", 1: "Senin", 2: "Selasa", 3: "Rabu",
              4: "Kamis", 5: "Jumat", 6: "Sabtu"}

# Override query manual untuk venue yang namanya ambigu / terlalu panjang
QUERY_OVERRIDE = {
    "Batavia (Kota Tua)":                    "Kawasan Kota Tua Jakarta",
    "Lubang Buaya":                          "Monumen Lubang Buaya Jakarta",
    "Gedung Gajah":                          "Museum Nasional Indonesia Gedung Gajah",
    "Sunda Kelapa - Batavia":               "Pelabuhan Sunda Kelapa Jakarta",
    "Halilintar":                            "Halilintar Dufan Ancol Jakarta",
    "Wahana Kicir-Kicir (Power Surge)":     "Kicir-kicir Dufan Ancol",
    "Treasure Land (Dufan)":                "Treasure Land Dufan Ancol",
    "Monumen Tragedi 12 Mei":               "Monumen Tragedi 12 Mei 1998 Trisakti",
    "Pantai Mutiara":                        "Pantai Mutiara Jakarta Utara",
    "Pasir putih":                           "Pantai Pasir Putih Ancol Jakarta",
    "Pentas Lumba2, Paus Putih, dan Singa Laut": "Pentas lumba-lumba Sea World Ancol",
    "Vihara Mahavira Graha Pusat VMGP":     "Vihara Mahavira Graha Jakarta",
    "Vihara Pitakananda":                   "Vihara Pitakananda Jakarta",
    "KMB Dharmayana":                        "KMB Dharmayana Vihara Jakarta",
    "Anjungan Bali":                         "Anjungan Bali TMII",
    "Anjungan Bangka Belitung":              "Anjungan Bangka Belitung TMII",
    "Anjungan Kalimantan Timur":             "Anjungan Kalimantan Timur TMII",
    "Anjungan Sumatera Selatan":             "Anjungan Sumatera Selatan TMII",
    "monumen persahabatan.TMII":             "Monumen Persahabatan TMII Jakarta",
    "VOC Galangan":                          "Museum Bahari Galangan VOC Jakarta",
    "Taman menteng":                         "Taman Menteng Jakarta Pusat",
}


def search_place_id(query, lat, lon, api_key, radius=800):
    url = f"{BASE}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName",
    }
    body = {
        "textQuery": query,
        "locationBias": {
            "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius}
        },
        "maxResultCount": 1,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        places = r.json().get("places", [])
        return places[0]["id"] if places else None
    except Exception:
        return None


def get_place_details(place_id, api_key):
    url = f"{BASE}/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join([
            "regularOpeningHours", "currentOpeningHours",
            "rating", "userRatingCount", "priceLevel",
            "editorialSummary", "types", "primaryType",
            "websiteUri", "goodForChildren", "nationalPhoneNumber",
            "businessStatus", "accessibilityOptions", "parkingOptions",
            "paymentOptions", "restroom", "photos", "addressComponents",
        ]),
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()

        oh_data = data.get("regularOpeningHours") or data.get("currentOpeningHours") or {}
        periods = oh_data.get("periods", [])
        hours = {d: None for d in DAYS_ID}
        # Deteksi 24 jam: semua period tidak punya close (1 period global atau 7 per hari)
        is_24h = len(periods) > 0 and all("close" not in p for p in periods)
        if is_24h:
            for d in DAYS_ID:
                hours[d] = ("00:00", "23:59")
        else:
            for p in periods:
                day_num = p.get("open", {}).get("day")
                day_id = GDAY_TO_ID.get(day_num)
                if not day_id:
                    continue
                o, c = p.get("open", {}), p.get("close", {})
                oh, om = o.get("hour", 0), o.get("minute", 0)
                ch, cm = c.get("hour", 0), c.get("minute", 0)
                hours[day_id] = (f"{oh:02d}:{om:02d}", f"{ch:02d}:{cm:02d}")

        sublocality, locality = None, None
        for comp in data.get("addressComponents", []):
            types = comp.get("types", [])
            if "administrative_area_level_4" in types:
                sublocality = comp.get("longText")
            elif "administrative_area_level_2" in types:
                locality = comp.get("longText")

        photos = data.get("photos", [])
        photo_ref = photos[0].get("name") if photos else None
        acc = data.get("accessibilityOptions", {})
        parking = data.get("parkingOptions", {})
        payment = data.get("paymentOptions", {})

        return {
            "hours": hours,
            "rating": data.get("rating"),
            "user_rating_count": data.get("userRatingCount"),
            "price_level": data.get("priceLevel"),
            "description": data.get("editorialSummary", {}).get("text"),
            "types": data.get("types", []),
            "primary_type": data.get("primaryType"),
            "website": data.get("websiteUri"),
            "phone": data.get("nationalPhoneNumber"),
            "good_for_children": data.get("goodForChildren"),
            "business_status": data.get("businessStatus"),
            "wheelchair_accessible": acc.get("wheelchairAccessibleEntrance"),
            "has_parking": any(parking.values()) if parking else None,
            "accepts_cashless": payment.get("acceptsCreditCards") or payment.get("acceptsDebitCards"),
            "has_restroom": data.get("restroom"),
            "photo_ref": photo_ref,
            "sublocality": sublocality,
            "locality": locality,
        }
    except Exception:
        return None


def apply_default_hours(df, idx):
    from enrich_hours_google import DEFAULT_HOURS
    cat = df.at[idx, "venue_category"]
    if cat not in DEFAULT_HOURS:
        return
    buka, tutup = DEFAULT_HOURS[cat]
    for day in DAYS_ID:
        df.at[idx, f"{day}_buka"] = buka
        df.at[idx, f"{day}_tutup"] = tutup
    df.at[idx, "hours_source"] = "default_category"


def main():
    api_key = os.environ.get("GOOGLE_PLACES_KEY", "")
    if not api_key:
        raise RuntimeError("Set GOOGLE_PLACES_KEY")

    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV,
                     dtype={"sublocality": "object", "locality": "object",
                            "primary_type": "object", "business_status": "object",
                            "photo_ref": "object"})

    # Target: venue default_category ATAU google_places tapi semua jam Tutup
    # (terjadi saat venue masuk via Google batch setelah enrich_hours jalan)
    DAYS_ID_LOCAL = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
    buka_cols = [f"{d}_buka" for d in DAYS_ID_LOCAL]
    mask_all_tutup = df[buka_cols].apply(lambda row: (row == "Tutup").all(), axis=1)
    mask_target = (df["hours_source"] == "default_category") | (
        (df["hours_source"] == "google_places") & mask_all_tutup
    )
    targets = df[mask_target]
    print(f"Venue target retry: {len(targets)} (default_category + google_places all-Tutup)")

    n_ok, n_miss = 0, 0

    for i, (idx, row) in enumerate(targets.iterrows()):
        name = row["name"]
        lat, lon = row["latitude"], row["longitude"]

        # Pilih query: override manual atau nama asli
        query = QUERY_OVERRIDE.get(name, f"{name} Jakarta")

        # Cari place_id dengan radius lebih besar (1km) untuk venue yang susah
        place_id = search_place_id(query, lat, lon, api_key, radius=1000)
        time.sleep(0.3)

        if not place_id:
            # Coba fallback: nama pendek (ambil kata pertama 3 kata)
            short = " ".join(name.split()[:3])
            place_id = search_place_id(f"{short} Jakarta", lat, lon, api_key, radius=1500)
            time.sleep(0.3)

        if not place_id:
            n_miss += 1
            print(f"  MISS: {name}")
            continue

        details = get_place_details(place_id, api_key)
        time.sleep(0.3)

        if not details:
            n_miss += 1
            print(f"  MISS (no details): {name}")
            continue

        hours = details.get("hours", {})
        filled_days = sum(1 for v in hours.values() if v is not None)

        if filled_days < 2:
            # Tetap pakai default, tapi update field lain yang berhasil
            apply_default_hours(df, idx)
        else:
            for day in DAYS_ID:
                val = hours.get(day)
                df.at[idx, f"{day}_buka"] = val[0] if val else "Tutup"
                df.at[idx, f"{day}_tutup"] = val[1] if val else "Tutup"
            df.at[idx, "hours_source"] = "google_places"

        # Update semua field non-jam
        df.at[idx, "google_rating"] = details.get("rating") or df.at[idx, "google_rating"]
        df.at[idx, "google_rating_count"] = details.get("user_rating_count") or df.at[idx, "google_rating_count"]
        df.at[idx, "price_level"] = details.get("price_level") or df.at[idx, "price_level"]
        df.at[idx, "description"] = details.get("description") or df.at[idx, "description"]
        df.at[idx, "good_for_children"] = details.get("good_for_children")
        df.at[idx, "primary_type"] = details.get("primary_type") or df.at[idx, "primary_type"]
        df.at[idx, "business_status"] = details.get("business_status") or df.at[idx, "business_status"]
        df.at[idx, "wheelchair_accessible"] = details.get("wheelchair_accessible")
        df.at[idx, "has_parking"] = details.get("has_parking")
        df.at[idx, "accepts_cashless"] = details.get("accepts_cashless")
        df.at[idx, "has_restroom"] = details.get("has_restroom")
        df.at[idx, "photo_ref"] = details.get("photo_ref") or df.at[idx, "photo_ref"]
        df.at[idx, "sublocality"] = details.get("sublocality") or df.at[idx, "sublocality"]
        df.at[idx, "locality"] = details.get("locality") or df.at[idx, "locality"]
        if details.get("website") and not df.at[idx, "References"]:
            df.at[idx, "References"] = details["website"]

        n_ok += 1
        print(f"  OK [{filled_days} hari]: {name}")

    tmp = config.MERGED_VENUES_ENRICHED_CSV + ".tmp"
    df.to_csv(tmp, index=False)
    try:
        os.replace(tmp, config.MERGED_VENUES_ENRICHED_CSV)
    except PermissionError:
        shutil.move(tmp, config.MERGED_VENUES_ENRICHED_CSV)

    print(f"\nRetry selesai: ok={n_ok} miss={n_miss}")
    remaining = df[df["hours_source"] == "default_category"]
    print(f"Masih default_category: {len(remaining)}")
    print(f"Coverage business_status: {df['business_status'].notna().sum()}/{len(df)}")
    print(f"Coverage sublocality: {df['sublocality'].notna().sum()}/{len(df)}")


if __name__ == "__main__":
    main()

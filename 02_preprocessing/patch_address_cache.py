"""
Patch: ambil addressComponents dari Google Places API untuk venue yang
sublocality/locality masih None di cache. Cache simpan parsed dict, bukan
raw API response, sehingga fix parse logic harus re-fetch dari API.

Hanya fetch venue yang cache-nya ada tapi sublocality/locality masih None.
Hemat kuota: skip venue yang sudah terisi.
"""
import json
import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

BASE = "https://places.googleapis.com/v1"
CACHE_DIR = os.path.join(os.path.dirname(config.MERGED_VENUES_ENRICHED_CSV),
                         "google_cache")


def search_place_id(name, lat, lon, api_key):
    url = f"{BASE}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName",
    }
    body = {
        "textQuery": f"{name} Jakarta",
        "locationBias": {
            "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": 500}
        },
        "maxResultCount": 1,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        places = r.json().get("places", [])
        return places[0]["id"] if places else None
    except Exception:
        return None


def fetch_address(place_id, api_key):
    """Ambil hanya addressComponents untuk venue tertentu."""
    url = f"{BASE}/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "addressComponents",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None, None
        comps = r.json().get("addressComponents", [])
        sublocality, locality = None, None
        for comp in comps:
            types = comp.get("types", [])
            if "administrative_area_level_4" in types:
                sublocality = comp.get("longText")
            elif "administrative_area_level_2" in types:
                locality = comp.get("longText")
        return sublocality, locality
    except Exception:
        return None, None


def main():
    api_key = os.environ.get("GOOGLE_PLACES_KEY", "")
    if not api_key:
        raise RuntimeError("Set GOOGLE_PLACES_KEY")

    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV,
                     dtype={"sublocality": "object", "locality": "object"})
    # Pastikan kolom string, bukan float64 (pandas default NaN-only kolom ke float)
    df["sublocality"] = df["sublocality"].astype("object")
    df["locality"] = df["locality"].astype("object")
    print(f"Total venue: {len(df)}")

    n_patch, n_skip, n_miss = 0, 0, 0

    for i, (idx, row) in enumerate(df.iterrows()):
        vid = str(row["venue_id"]).replace("/", "_")
        cache_path = os.path.join(CACHE_DIR, f"{vid}.json")

        if not os.path.exists(cache_path):
            n_miss += 1
            continue

        with open(cache_path, encoding="utf-8") as f:
            cached = json.load(f)

        if cached is None:
            n_miss += 1
            continue

        # Skip jika sudah terisi
        if cached.get("sublocality") or cached.get("locality"):
            n_skip += 1
            if cached.get("sublocality"):
                df.at[idx, "sublocality"] = cached["sublocality"]
            if cached.get("locality"):
                df.at[idx, "locality"] = cached["locality"]
            continue

        # Perlu fetch: cari place_id dulu
        place_id = search_place_id(row["name"], row["latitude"], row["longitude"], api_key)
        time.sleep(0.3)
        if not place_id:
            n_miss += 1
            continue

        sublocality, locality = fetch_address(place_id, api_key)
        time.sleep(0.3)

        # Update cache
        cached["sublocality"] = sublocality
        cached["locality"] = locality
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cached, f)

        # Update dataframe
        df.at[idx, "sublocality"] = sublocality
        df.at[idx, "locality"] = locality
        n_patch += 1

        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(df)} | patch:{n_patch} skip:{n_skip} miss:{n_miss}")

    # Simpan
    tmp = config.MERGED_VENUES_ENRICHED_CSV + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, config.MERGED_VENUES_ENRICHED_CSV)

    print(f"\nSelesai: patch={n_patch} skip={n_skip} miss={n_miss}")
    print(f"Coverage sublocality: {df['sublocality'].notna().sum()}/{len(df)}")
    print(f"Coverage locality: {df['locality'].notna().sum()}/{len(df)}")


if __name__ == "__main__":
    main()

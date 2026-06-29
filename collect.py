"""
Kumpulkan destinasi wisata Jakarta dari OpenStreetMap (Overpass API).

Legal & gratis: OSM data berlisensi ODbL, boleh dipakai dengan atribusi.
Mengganti scraping TripAdvisor yang melanggar ToS mereka.

Output: data/venues_raw.csv dengan kolom inti
    venue_id, name, venue_category, latitude, longitude
"""
import csv
import os
import time

import requests

import config


def build_query(bbox, key, values):
    """Query Overpass-QL single-line untuk SATU filter kategori.

    Query gabungan multi-statement bikin mod_security overpass-api.de
    balas 406. Jadi pisah per filter, single-line, panggil bergiliran.
    """
    s, w, n, e = bbox
    box = f"({s},{w},{n},{e})"
    if values is None:
        sel = f'["{key}"]["name"]'
    else:
        regex = "|".join(values)
        sel = f'["{key}"~"^({regex})$"]["name"]'
    body = f"node{sel}{box};way{sel}{box};"
    return f"[out:json][timeout:120];({body});out center tags;"


HEADERS = {
    # Overpass tolak request tanpa User-Agent. Header Accept JANGAN diset
    # ke application/json -> bikin 406 Not Acceptable. Biar default.
    "User-Agent": "JakartaWisataRec/1.0",
}


def fetch(query, retries=2):
    """Kirim query ke Overpass; coba tiap endpoint, retry kalau gagal."""
    last = None
    for url in config.OVERPASS_URLS:
        for attempt in range(retries):
            try:
                resp = requests.post(url, data={"data": query},
                                     headers=HEADERS, timeout=180)
            except requests.RequestException as exc:
                print(f"  {url} error: {exc}")
                break
            if resp.status_code == 200:
                return resp.json()
            last = resp
            print(f"  {url} status {resp.status_code}, retry {attempt + 1}/{retries} ...")
            time.sleep(5 * (attempt + 1))
    if last is not None:
        last.raise_for_status()
    raise RuntimeError("Semua endpoint Overpass gagal.")


def derive_category(tags):
    """Ambil kategori venue dari tag OSM (prioritas tourism > leisure > ...)."""
    for key in ("tourism", "leisure", "historic", "amenity"):
        if key in tags:
            return f"{key}:{tags[key]}"
    return "unknown"


def parse(elements):
    """Konversi elemen Overpass -> list dict baris venue."""
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        # node punya lat/lon langsung; way pakai 'center'.
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        rows.append({
            "venue_id": f'{el["type"]}/{el["id"]}',
            "name": name,
            "venue_category": derive_category(tags),
            "latitude": lat,
            "longitude": lon,
            # tag jam operasional OSM (format opening_hours). Bisa kosong.
            "opening_hours": tags.get("opening_hours", ""),
            # link sumber/referensi.
            "website": tags.get("website") or tags.get("contact:website", ""),
            "wikipedia": tags.get("wikipedia", ""),
            "wikidata": tags.get("wikidata", ""),
            "osm_url": f'https://www.openstreetmap.org/{el["type"]}/{el["id"]}',
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
        })
    return rows


def dedupe(rows):
    """Buang duplikat nama+koordinat (node & way bisa overlap)."""
    seen, out = set(), []
    for r in rows:
        key = (r["name"].strip().lower(), round(r["latitude"], 4), round(r["longitude"], 4))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main():
    os.makedirs("data", exist_ok=True)
    all_elements = []
    for key, values in config.TOURISM_FILTERS.items():
        query = build_query(config.JAKARTA_BBOX, key, values)
        print(f"Query Overpass: {key} ...")
        data = fetch(query)
        els = data.get("elements", [])
        print(f"  {len(els)} elemen.")
        all_elements.extend(els)
        time.sleep(8)  # jeda sopan, hindari 429 rate-limit
    rows = dedupe(parse(all_elements))
    print(f"Dapat {len(rows)} venue unik.")

    with open(config.RAW_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["venue_id", "name", "venue_category", "latitude",
                           "longitude", "opening_hours", "website",
                           "wikipedia", "wikidata", "osm_url", "maps_url"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Tersimpan -> {config.RAW_CSV}")


if __name__ == "__main__":
    main()

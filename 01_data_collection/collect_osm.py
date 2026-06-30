"""
Kumpulkan destinasi wisata Jakarta dari OpenStreetMap (Overpass API).

Legal & gratis: OSM data berlisensi ODbL, boleh dipakai dengan atribusi.
Mengganti scraping TripAdvisor yang melanggar ToS mereka.

Output: data/venues_raw.csv dengan kolom inti
    venue_id, name, venue_category, latitude, longitude
"""
import csv
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def build_query(bbox, key, values, area_name=None, area_admin_level=None):
    """Query Overpass-QL single-line untuk SATU filter kategori.

    Query gabungan multi-statement bikin mod_security overpass-api.de
    balas 406. Jadi pisah per filter, single-line, panggil bergiliran.

    Pakai boundary administratif asli (area_name+admin_level) bila tersedia,
    bukan bounding box persegi -> bbox persegi Jakarta overlap sebagian
    wilayah Bekasi/Depok/Tangerang sehingga venue luar Jakarta ikut tertarik.
    """
    if values is None:
        sel = f'["{key}"]["name"]'
    else:
        regex = "|".join(values)
        sel = f'["{key}"~"^({regex})$"]["name"]'

    if area_name is not None:
        area_def = f'area["name"="{area_name}"]["admin_level"="{area_admin_level}"]->.a;'
        body = f"node{sel}(area.a);way{sel}(area.a);"
        return f"[out:json][timeout:120];{area_def}({body});out center tags;"

    s, w, n, e = bbox
    box = f"({s},{w},{n},{e})"
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


def _haversine_m(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    r = 6371000
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


_GENERIC_WORDS = {
    "taman", "museum", "monumen", "patung", "lapangan", "kawasan", "gedung",
    "anjungan", "menara", "tugu", "park", "playground", "garden", "blok",
    "kompleks", "komplek", "pertigaan", "ruang", "habitat", "jogging", "kota",
}


def _shared_word(name_a, name_b):
    """True kalau kedua nama berbagi kata khas non-generik (cth 'Monas Selatan' vs 'Taman Monas' -> 'monas')."""
    wa = {w for w in name_a.lower().split() if len(w) > 3 and w not in _GENERIC_WORDS}
    wb = {w for w in name_b.lower().split() if len(w) > 3 and w not in _GENERIC_WORDS}
    return bool(wa & wb)


def _row_priority(r):
    """Skor representative cluster: kategori spesifik > punya referensi > nama panjang."""
    has_ref = bool(r["website"] or r["wikipedia"] or r["wikidata"])
    specific_category = not r["venue_category"].endswith(":yes")
    return (specific_category, has_ref, len(r["name"]))


def dedupe_clusters(rows, radius_m=700):
    """Gabung venue beda nama tapi entitas sama (cth 4 gerbang Monas jadi 1).

    Cluster transitif (BFS): venue berjarak <= radius_m DAN nama nyambung
    (kata kunci sama) digabung jadi grup, walau tak semua pasangan dalam
    grup berjarak dekat langsung (cth Utara-Selatan jauh tapi sama-sama
    dekat Taman Monas yang jadi penghubung). Pilih 1 representative per
    cluster (kategori paling spesifik, ada referensi, nama paling deskriptif).
    """
    n = len(rows)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dist = _haversine_m(rows[i]["latitude"], rows[i]["longitude"],
                                 rows[j]["latitude"], rows[j]["longitude"])
            if dist <= radius_m and _shared_word(rows[i]["name"], rows[j]["name"]):
                adj[i].append(j)
                adj[j].append(i)

    visited = [False] * n
    out = []
    for i in range(n):
        if visited[i]:
            continue
        stack, cluster_idx = [i], []
        visited[i] = True
        while stack:
            cur = stack.pop()
            cluster_idx.append(cur)
            for nb in adj[cur]:
                if not visited[nb]:
                    visited[nb] = True
                    stack.append(nb)
        cluster = [rows[k] for k in cluster_idx]
        out.append(max(cluster, key=_row_priority))
    return out


def main():
    os.makedirs("data/raw", exist_ok=True)
    all_elements = []
    for key, values in config.TOURISM_FILTERS.items():
        print(f"Query Overpass: {key} ...")
        try:
            query = build_query(config.JAKARTA_BBOX, key, values,
                                 area_name=config.JAKARTA_AREA_NAME,
                                 area_admin_level=config.JAKARTA_AREA_ADMIN_LEVEL)
            data = fetch(query)
        except Exception as exc:
            print(f"  area query gagal ({exc}), fallback ke bbox ...")
            query = build_query(config.JAKARTA_BBOX, key, values)
            data = fetch(query)
        els = data.get("elements", [])
        print(f"  {len(els)} elemen.")
        all_elements.extend(els)
        time.sleep(8)

    rows = parse(all_elements)
    print(f"Total elemen dari Overpass: {len(rows)} (belum dedupe, mentah)")

    with open(config.RAW_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["venue_id", "name", "venue_category", "latitude",
                           "longitude", "opening_hours", "website",
                           "wikipedia", "wikidata", "osm_url", "maps_url"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Tersimpan mentah -> {config.RAW_CSV}")


if __name__ == "__main__":
    main()

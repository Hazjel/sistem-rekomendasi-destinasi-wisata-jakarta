"""
Kumpulkan hotel/penginapan Jakarta dari OpenStreetMap (Overpass API).

Dipisah dari collect_osm.py (venue wisata) karena peran beda: hotel jadi
titik berangkat/pulang itinerary (next phase, UI website), bukan venue yang
diskor/direkomendasikan oleh recommend.py.

Reuse build_query/fetch/parse/dedupe dari collect_osm.py -- pola identik,
cuma filter kategori & output path beda.

Output: data/raw/hotels_raw.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from collect_osm import build_query, fetch, parse, dedupe


def main():
    os.makedirs(os.path.dirname(config.HOTEL_RAW_CSV), exist_ok=True)
    all_elements = []
    for key, values in config.HOTEL_FILTERS.items():
        print(f"Query Overpass hotel: {key} ...")
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

    rows = dedupe(parse(all_elements))
    print(f"Dapat {len(rows)} hotel unik.")

    with open(config.HOTEL_RAW_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["venue_id", "name", "venue_category", "latitude",
                           "longitude", "opening_hours", "website",
                           "wikipedia", "wikidata", "osm_url", "maps_url"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Tersimpan -> {config.HOTEL_RAW_CSV}")


if __name__ == "__main__":
    main()

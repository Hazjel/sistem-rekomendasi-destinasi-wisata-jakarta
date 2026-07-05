"""
Re-fetch daftar foto Google Places untuk venue tertentu.

Enrich awal hanya menyimpan foto PERTAMA (photos[0]) yang kadang bukan foto
representatif (mis. Batavia/Kota Tua fotonya ilustrasi). Script ini mengambil
beberapa foto teratas dari Places Details, mengunduh thumbnail tiap kandidat ke
folder review, lalu (opsional) menetapkan photo_ref pilihan ke dataset.

Pakai:
  # 1) lihat kandidat foto untuk venue tertentu (unduh ke scratch/photo_review/)
  python src/preprocessing/refetch_photos.py --list 27507

  # 2) setelah memilih (mis. kandidat index 2), tetapkan ke dataset
  python src/preprocessing/refetch_photos.py --set 27507 --index 2

Butuh GOOGLE_PLACES_KEY di .env. Mengubah kolom photo_ref di
merged_venues_enriched.csv (pipeline — bukan edit CSV manual).
"""
import argparse
import os
import sys

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
API_KEY = os.environ.get("GOOGLE_PLACES_KEY", "")
BASE = "https://places.googleapis.com/v1"
REVIEW_DIR = os.path.join(os.path.dirname(__file__), "..", "..",
                          "data", "photo_review")


def _place_id(name, lat, lon):
    """Text Search -> place_id (venue mungkin tak punya place_id tersimpan)."""
    r = requests.post(
        f"{BASE}/places:searchText",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": API_KEY,
                 "X-Goog-FieldMask": "places.id"},
        json={"textQuery": f"{name} Jakarta",
              "locationBias": {"circle": {
                  "center": {"latitude": lat, "longitude": lon},
                  "radius": 500.0}}},
        timeout=15)
    places = r.json().get("places", [])
    return places[0]["id"] if places else None


def _photo_refs(place_id, limit=10):
    """Ambil daftar photo resource-name (photos[].name)."""
    r = requests.get(
        f"{BASE}/places/{place_id}",
        headers={"X-Goog-Api-Key": API_KEY, "X-Goog-FieldMask": "photos"},
        timeout=15)
    return [p["name"] for p in r.json().get("photos", [])[:limit]]


def _download(ref, path, w=600):
    r = requests.get(f"{BASE}/{ref}/media",
                     params={"maxWidthPx": w, "key": API_KEY}, timeout=20)
    if r.status_code == 200:
        with open(path, "wb") as f:
            f.write(r.content)
        return True
    return False


def cmd_list(venue_id):
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    row = df[df["venue_id"].astype(str) == str(venue_id)]
    if row.empty:
        print(f"venue_id {venue_id} tidak ada"); return
    r = row.iloc[0]
    pid = _place_id(r["name"], r["latitude"], r["longitude"])
    if not pid:
        print("place_id tidak ditemukan"); return
    refs = _photo_refs(pid)
    print(f"{r['name']} — {len(refs)} kandidat foto (place_id {pid})")
    os.makedirs(REVIEW_DIR, exist_ok=True)
    for i, ref in enumerate(refs):
        path = os.path.join(REVIEW_DIR, f"{venue_id}_{i}.jpg")
        ok = _download(ref, path)
        print(f"  [{i}] {'OK  ' + path if ok else 'GAGAL'}  {ref[:60]}…")
    print(f"\nLihat folder {REVIEW_DIR}, lalu:")
    print(f"  python src/preprocessing/refetch_photos.py --set {venue_id} --index <N>")


def cmd_set(venue_id, index):
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    row = df[df["venue_id"].astype(str) == str(venue_id)]
    if row.empty:
        print(f"venue_id {venue_id} tidak ada"); return
    r = row.iloc[0]
    pid = _place_id(r["name"], r["latitude"], r["longitude"])
    refs = _photo_refs(pid)
    if index >= len(refs):
        print(f"index {index} di luar jangkauan (0..{len(refs)-1})"); return
    new_ref = refs[index]
    df.loc[row.index, "photo_ref"] = new_ref
    df.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
    print(f"photo_ref '{r['name']}' -> kandidat [{index}]")
    print(f"  {new_ref}")
    # buang cache foto lama supaya API fetch ulang
    for w in (400, 800, 1600):
        p = os.path.join(os.path.dirname(__file__), "..", "..",
                         "data", "photo_cache", f"{venue_id}_{w}.jpg")
        if os.path.exists(p):
            os.remove(p)
    print("Cache foto lama dihapus. Restart uvicorn agar dataset ter-reload.")


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("Set GOOGLE_PLACES_KEY di .env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", metavar="VENUE_ID")
    ap.add_argument("--set", metavar="VENUE_ID")
    ap.add_argument("--index", type=int)
    a = ap.parse_args()
    if a.list:
        cmd_list(a.list)
    elif a.set is not None and a.index is not None:
        cmd_set(a.set, a.index)
    else:
        ap.print_help()

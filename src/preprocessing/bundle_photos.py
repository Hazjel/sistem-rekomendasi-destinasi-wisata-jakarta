"""Unduh foto Google Places semua venue -> file statis untuk frontend.

Output: web-wisata-jakarta/public/photos/{venue_id}.jpg
Dipakai agar foto di-serve sebagai aset statis Vercel (tanpa GOOGLE_PLACES_KEY
runtime, tanpa proxy backend, tanpa cache ephemeral serverless).

Idempoten: skip venue yang filenya sudah ada. Jalankan sekali sebelum deploy.
Butuh GOOGLE_PLACES_KEY di .env.
"""
import os
import sys
import time

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

load_dotenv()
KEY = os.environ.get("GOOGLE_PLACES_KEY", "")
# Frontend repo diasumsikan sejajar dengan repo model di d:/humic/.
OUT_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "web-wisata-jakarta", "public", "photos"))
WIDTH = 800


def main():
    if not KEY:
        print("GOOGLE_PLACES_KEY kosong di .env — tak bisa unduh.")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(config.CLUSTERED_VENUES_CSV)
    df = df[df["photo_ref"].notna()]
    print(f"Venue dgn photo_ref: {len(df)} | output: {OUT_DIR}")

    ok = skip = fail = 0
    for _, r in df.iterrows():
        vid = str(r["venue_id"])
        dst = os.path.join(OUT_DIR, f"{vid}.jpg")
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            skip += 1
            continue
        url = f"https://places.googleapis.com/v1/{r['photo_ref']}/media"
        try:
            resp = requests.get(url, params={"maxWidthPx": WIDTH, "key": KEY},
                                timeout=20)
        except requests.RequestException as e:
            print(f"  [gagal] {vid}: {e}")
            fail += 1
            continue
        if resp.status_code != 200:
            print(f"  [gagal] {vid}: HTTP {resp.status_code}")
            fail += 1
            continue
        with open(dst, "wb") as f:
            f.write(resp.content)
        ok += 1
        if ok % 20 == 0:
            print(f"  ... {ok} terunduh")
        time.sleep(0.15)      # sopan ke Google

    print(f"\nSelesai. Baru: {ok} | skip (sudah ada): {skip} | gagal: {fail}")
    total = len([f for f in os.listdir(OUT_DIR) if f.endswith('.jpg')])
    print(f"Total foto di {OUT_DIR}: {total}")


if __name__ == "__main__":
    main()

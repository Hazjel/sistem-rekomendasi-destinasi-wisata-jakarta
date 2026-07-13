"""Entry point serverless Vercel — ekspor FastAPI `app` dari src/api/api.py.

Vercel Python menjalankan objek ASGI `app` di file ini sebagai function.
Semua request /api/* dialihkan ke sini oleh vercel.json.

CATATAN: backend ini load dataset CSV + optimizer saat import (cold start).
Di serverless, cold start terjadi berkala; request pertama setelah idle lambat.
Rute optimasi multi-hari (GWO-TS 5 hari) bisa mendekati batas waktu function.
"""
import os
import sys

# root repo = satu level di atas api/ (api/ -> root)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# PENTING: config.py memakai path CSV RELATIF ("data/processed/..."). Di Vercel
# serverless working directory bukan root repo, jadi read_csv gagal -> function
# crash saat import. chdir ke ROOT agar path relatif tetap valid.
os.chdir(ROOT)

from src.api.api import app  # noqa: E402  (app ASGI yang dijalankan Vercel)

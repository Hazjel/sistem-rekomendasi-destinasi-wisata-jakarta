"""Entry point serverless Vercel — ekspor FastAPI `app` dari src/api/api.py.

Vercel Python menjalankan objek ASGI `app` di file ini sebagai function.
Semua request /api/* dialihkan ke sini oleh vercel.json.

CATATAN: backend ini load dataset CSV + optimizer saat import (cold start).
Di serverless, cold start terjadi berkala; request pertama setelah idle lambat.
Rute optimasi multi-hari (GWO-TS 5 hari) bisa mendekati batas waktu function.
"""
import os
import sys

# root repo = dua level di atas file ini (api/ -> root)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.api.api import app  # noqa: E402  (app ASGI yang dijalankan Vercel)

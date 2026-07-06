"""
REST API itinerary wisata Jakarta — FASE 1 CBF + FASE 2 GA/PSO/Hybrid.

Jalankan dari root project:
    uvicorn src.api.api:app --reload

Endpoint:
    GET  /venues            — 162 venue (grid Home + mode manual + peta)
    GET  /venues/{id}       — detail satu venue
    GET  /venues/{id}/photo — proxy foto Google Places (key server-side, aman)
    GET  /hotels            — 181 hotel (dropdown titik menginap)
    POST /itinerary         — susun itinerary multi-hari
    GET  /health

Frontend (repo terpisah, Vite+React) jalan di http://localhost:5173 — CORS
di-allow utk origin itu.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

import itinerary_service as svc

# .env di root project (GOOGLE_PLACES_KEY) — utk proxy foto Places
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
_PLACES_KEY = os.environ.get("GOOGLE_PLACES_KEY", "")
_PHOTO_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..",
                                "data", "photo_cache")
os.makedirs(_PHOTO_CACHE_DIR, exist_ok=True)

app = FastAPI(title="Sistem Rekomendasi Destinasi Wisata Jakarta",
              description="CBF (TF-IDF+MMR) + optimasi rute GA/PSO/Hybrid — "
                          "multi-day itinerary (TTDP)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DAYS = {"Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"}


class ItineraryRequest(BaseModel):
    preference_text: str | None = Field(
        None, description="Preferensi turis, mis. 'museum sejarah budaya'. "
                          "Wajib utk mode otomatis; opsional utk mode manual.")
    budget: str = Field("menengah", description="hemat / menengah / bebas")
    n_days: int = Field(2, ge=1, le=5)
    start_day: str = Field("Sabtu", description="Senin..Minggu")
    hotel_id: int | None = Field(None, description="dari GET /hotels; "
                                                   "None -> pusat kota")
    venue_ids: list[str] | None = Field(
        None, description="Mode MANUAL: daftar venue_id pilihan user "
                          "(dari GET /venues). None -> mode otomatis (CBF).")
    algorithm: str = Field(
        "auto", description="auto (default — pilih otomatis dari hasil "
                            "eksperimen: hybrid utk 1-3 hari, ga utk 4-5) "
                            "/ ga / pso / hybrid")
    vehicle: str = Field(
        "mobil", description="moda kendaraan: mobil / motor "
                            "(mempengaruhi estimasi waktu tempuh & jumlah "
                            "destinasi yang muat per hari)")


@app.get("/venues")
def venues():
    return svc.list_venues()


@app.get("/venues/{venue_id}")
def venue_detail(venue_id: str):
    d = svc.venue_detail(venue_id)
    if d is None:
        raise HTTPException(404, f"venue_id tidak dikenal: {venue_id}")
    return d


@app.get("/venues/{venue_id}/similar")
def venue_similar(venue_id: str, k: int = 4):
    out = svc.similar_venues(venue_id, k=min(max(k, 1), 12))
    if out is None:
        raise HTTPException(404, f"venue_id tidak dikenal: {venue_id}")
    return out


@app.get("/venues/{venue_id}/photo")
def venue_photo(venue_id: str, w: int = 800):
    """Proxy foto Google Places — key dipakai server-side (tidak bocor ke
    browser). Hasil di-cache lokal supaya tidak fetch berulang."""
    ref = svc.photo_ref_of(venue_id)
    if ref is None:
        raise HTTPException(404, "venue tidak punya foto")

    cache_path = os.path.join(_PHOTO_CACHE_DIR, f"{venue_id}_{w}.jpg")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return Response(f.read(), media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=604800"})

    if not _PLACES_KEY:
        raise HTTPException(503, "GOOGLE_PLACES_KEY tidak diset di .env")
    url = f"https://places.googleapis.com/v1/{ref}/media"
    try:
        r = requests.get(url, params={"maxWidthPx": w, "key": _PLACES_KEY},
                         timeout=15)
    except requests.RequestException:
        raise HTTPException(502, "gagal mengambil foto dari Google")
    if r.status_code != 200:
        raise HTTPException(502, f"Google Places photo -> {r.status_code}")

    with open(cache_path, "wb") as f:
        f.write(r.content)
    return Response(r.content, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=604800"})


@app.get("/hotels")
def hotels():
    return svc.list_hotels()


@app.post("/itinerary")
def itinerary(req: ItineraryRequest):
    if req.budget not in ("hemat", "menengah", "bebas"):
        raise HTTPException(422, "budget harus hemat/menengah/bebas")
    if req.start_day not in DAYS:
        raise HTTPException(422, f"start_day harus salah satu {sorted(DAYS)}")
    try:
        return svc.build_itinerary(
            preference_text=req.preference_text, budget=req.budget,
            n_days=req.n_days, start_day=req.start_day,
            hotel_id=req.hotel_id, venue_ids=req.venue_ids,
            algorithm=req.algorithm, vehicle=req.vehicle)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/health")
def health():
    return {"status": "ok", "venues": len(svc.venues),
            "hotels": len(svc.hotels)}

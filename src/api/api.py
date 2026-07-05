"""
REST API itinerary wisata Jakarta — FASE 1 CBF + FASE 2 GA/PSO/Hybrid.

Jalankan dari root project:
    uvicorn src.api.api:app --reload

Endpoint:
    GET  /venues     — 162 venue (mode pilih-manual + peta)
    GET  /hotels     — 181 hotel (dropdown titik menginap)
    POST /itinerary  — susun itinerary multi-hari
    GET  /health

Frontend (repo terpisah, Vite+React) jalan di http://localhost:5173 — CORS
di-allow utk origin itu.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import itinerary_service as svc

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


@app.get("/venues")
def venues():
    return svc.list_venues()


@app.get("/venues/{venue_id}")
def venue_detail(venue_id: str):
    d = svc.venue_detail(venue_id)
    if d is None:
        raise HTTPException(404, f"venue_id tidak dikenal: {venue_id}")
    return d


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
            algorithm=req.algorithm)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/health")
def health():
    return {"status": "ok", "venues": len(svc.venues),
            "hotels": len(svc.hotels)}

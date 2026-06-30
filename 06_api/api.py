"""
REST API serving rekomendasi. Jalankan dari folder 06_api/:
    uvicorn api:app --reload
Atau dari root project:
    uvicorn 06_api.api:app --reload
Lalu:
    GET /recommend?lat=-6.1754&lon=106.8272&category=Museum&day=Sabtu&top_n=10
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, Query

from recommend import Recommender

app = FastAPI(title="Rekomendasi Destinasi Wisata Jakarta")
rec = Recommender()


@app.get("/recommend")
def recommend(
    lat: float = Query(..., description="Latitude posisi turis"),
    lon: float = Query(..., description="Longitude posisi turis"),
    category: str | None = Query(None, description="Kategori minat, mis. tourism:museum"),
    day: str | None = Query(None, description="Hari kunjungan, mis. Sabtu"),
    max_km: float = Query(25.0),
    top_n: int = Query(10, ge=1, le=50),
):
    df = rec.recommend(lat, lon, category=category, day=day,
                       max_km=max_km, top_n=top_n)
    return df.to_dict(orient="records")


@app.get("/health")
def health():
    return {"status": "ok", "venues": len(rec.df)}

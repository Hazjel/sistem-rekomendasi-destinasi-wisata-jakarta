"""
Service layer API itinerary — glue FASE 1 (CBF) + FASE 2 (GA/PSO/Hybrid).

Reuse penuh src/modeling/* (satu sumber kebenaran dgn notebook 06):
  - ContentBasedFilter : TF-IDF + Bayesian rating + filter budget + MMR
  - TTDPProblem        : time-budget decoding (lunch break, jam tutup hard)
  - run_ga/run_pso/run_hybrid : optimizer + 2-opt polish

Semua data (venue, hotel, time matrix) diload SEKALI saat modul diimport —
request berikutnya tinggal optimasi (~1-3 dtk GA).
"""
import os
import sys

import pandas as pd

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src", "modeling"))

import config
from cbf import ContentBasedFilter
from ga import run_ga
from hybrid import run_hybrid
from problem import TTDPProblem
from pso import run_pso

_ALGOS = {"ga": run_ga, "pso": run_pso, "hybrid": run_hybrid}

# --- load sekali saat startup ---
cbf = ContentBasedFilter()
hotels = pd.read_csv(config.HOTELS_CSV)
hotels = hotels.reset_index().rename(columns={"index": "hotel_id"})
venues = pd.read_csv(config.CLUSTERED_VENUES_CSV)


def list_venues():
    """Semua venue utk grid Home + mode pilih-manual + peta."""
    out = venues.copy()
    out["price_level"] = out["venue_category"].map(
        lambda c: config.CATEGORY_PRICE_LEVEL.get(
            c, config.CATEGORY_PRICE_LEVEL["DEFAULT"]))
    out["description_short"] = (out["description"].fillna("")
                                .str.slice(0, 160))
    out["has_photo"] = out["photo_ref"].notna()
    cols = ["venue_id", "name", "venue_category", "zone_id",
            "google_rating", "google_rating_count", "price_level",
            "latitude", "longitude",
            "time_spent_minutes", "description_short", "has_photo"]
    return out[cols].fillna(
        {"google_rating": 0, "google_rating_count": 0}).to_dict(orient="records")


def similar_venues(venue_id, k=4):
    """Top-k venue paling mirip (cosine TF-IDF dari CBF). None kalau id salah.

    Reuse matriks TF-IDF cbf._mat — di UI ditampilkan sebagai
    "Kamu mungkin juga suka" tanpa istilah teknis."""
    from sklearn.metrics.pairwise import cosine_similarity

    ids = cbf.df["venue_id"].astype(str).tolist()
    if str(venue_id) not in ids:
        return None
    row = ids.index(str(venue_id))
    sims = cosine_similarity(cbf._mat[row], cbf._mat).ravel()
    order = sims.argsort()[::-1]
    picked = [i for i in order if i != row][:k]

    detail = {str(v["venue_id"]): v for v in list_venues()}
    return [detail[ids[i]] for i in picked if ids[i] in detail]


def photo_ref_of(venue_id):
    """Google Places photo resource name utk venue. None kalau tak ada."""
    row = venues[venues["venue_id"].astype(str) == str(venue_id)]
    if row.empty:
        return None
    ref = row.iloc[0].get("photo_ref")
    return None if pd.isna(ref) else str(ref)


_DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def venue_detail(venue_id):
    """Detail lengkap satu venue utk halaman destinasi. None kalau tak ada."""
    row = venues[venues["venue_id"].astype(str) == str(venue_id)]
    if row.empty:
        return None
    r = row.iloc[0]
    hours = []
    for d in _DAYS_ID:
        buka, tutup = r.get(f"{d}_buka"), r.get(f"{d}_tutup")
        hours.append({"day": d,
                      "open": None if pd.isna(buka) else str(buka),
                      "close": None if pd.isna(tutup) else str(tutup)})
    return {
        "venue_id": r["venue_id"],
        "name": r["name"],
        "venue_category": r["venue_category"],
        "zone_id": int(r["zone_id"]),
        "google_rating": None if pd.isna(r["google_rating"]) else float(r["google_rating"]),
        "google_rating_count": None if pd.isna(r.get("google_rating_count")) else int(r["google_rating_count"]),
        "price_level": config.CATEGORY_PRICE_LEVEL.get(
            r["venue_category"], config.CATEGORY_PRICE_LEVEL["DEFAULT"]),
        "latitude": float(r["latitude"]),
        "longitude": float(r["longitude"]),
        "time_spent_minutes": None if pd.isna(r.get("time_spent_minutes")) else int(r["time_spent_minutes"]),
        "description": None if pd.isna(r.get("description")) else str(r["description"]),
        "address": None if pd.isna(r.get("address")) else str(r["address"]),
        "has_photo": not pd.isna(r.get("photo_ref")),
        "hours": hours,
    }


def list_hotels():
    """Semua hotel utk dropdown (hotel_id = index baris CSV, stabil)."""
    cols = ["hotel_id", "name", "google_rating", "latitude", "longitude"]
    return hotels[cols].fillna({"google_rating": 0}).to_dict(orient="records")


def _hhmm(minutes):
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def build_itinerary(preference_text=None, budget="menengah", n_days=2,
                    start_day="Sabtu", hotel_id=None, venue_ids=None,
                    algorithm="auto", seed=config.RANDOM_SEED):
    """Susun itinerary multi-hari. Returns dict siap di-JSON-kan.

    venue_ids None  -> mode OTOMATIS: kandidat dari CBF top-N (MMR)
    venue_ids [...] -> mode MANUAL (ala go-routes): user pilih sendiri;
                       satisfaction tetap dari CBF (preferensi boleh kosong ->
                       fallback popularitas Bayesian)
    algorithm "auto" -> pilih otomatis berdasar HASIL EKSPERIMEN dataset 162
                       (90 run/algoritma): Hybrid unggul problem kecil-menengah
                       (1-3 hari), GA unggul problem besar (4-5 hari) + tercepat.
                       Nilai eksplisit ga/pso/hybrid tetap didukung utk riset.
    """
    if not 1 <= n_days <= config.MAX_DAYS:
        raise ValueError(f"n_days harus 1..{config.MAX_DAYS}")
    if algorithm == "auto":
        algorithm = "hybrid" if n_days <= 3 else "ga"
    if algorithm not in _ALGOS:
        raise ValueError(f"algorithm harus 'auto' atau salah satu {list(_ALGOS)}")

    # --- kandidat + satisfaction ---
    if venue_ids:
        known = set(venues["venue_id"].astype(str))
        bad = [v for v in venue_ids if str(v) not in known]
        if bad:
            raise ValueError(f"venue_id tidak dikenal: {bad}")
        ids = list(venue_ids)
        scored = cbf.score(preference_text or None, budget)
        sat_all = dict(zip(scored["venue_id"], scored["satisfaction"]))
        # venue pilihan user di luar filter budget tetap dihormati (user tahu
        # harganya) — satisfaction fallback 0.5 netral kalau tak ada di scored
        sat = {v: float(sat_all.get(v, 0.5)) for v in ids}
    else:
        if not preference_text:
            raise ValueError("mode otomatis butuh preference_text")
        ids, sat = cbf.candidates(n_days, preference_text, budget)

    # --- hotel ---
    hotel = None
    if hotel_id is not None:
        row = hotels[hotels["hotel_id"] == hotel_id]
        if row.empty:
            raise ValueError(f"hotel_id tidak dikenal: {hotel_id}")
        hotel = row.iloc[0]

    # --- optimasi ---
    prob = TTDPProblem(ids, hotel=hotel, n_days=n_days, start_day=start_day,
                       satisfaction=sat)
    res = _ALGOS[algorithm](prob, seed=seed)
    d = prob.decode(res["best_perm"])

    # --- serialisasi ---
    vidx = venues.set_index("venue_id")
    days_out = []
    for di, day in enumerate(d["days"]):
        visits = []
        for v in day:
            item = {
                "type": ("break" if v.get("is_break")
                         else "return" if v["venue_id"] is None
                         else "visit"),
                "venue_id": v["venue_id"],
                "name": v["name"],
                "depart_prev": _hhmm(v["depart_prev"]),
                "travel_min": round(v["travel_min"], 1),
                "from_hotel": v["from_hotel"],
                "arrival": _hhmm(v["arrival"]),
                "start": _hhmm(v["start"]),
                "depart": _hhmm(v["depart"]),
                "wait_min": round(v["wait"], 1),
            }
            if item["type"] == "visit":
                r = vidx.loc[v["venue_id"]]
                item["latitude"] = float(r["latitude"])
                item["longitude"] = float(r["longitude"])
                item["venue_category"] = r["venue_category"]
            visits.append(item)
        days_out.append({"day_index": di + 1,
                         "day_name": prob.day_names[di],
                         "visits": visits})

    not_fitted = [
        {"venue_id": v, "name": vidx.loc[v]["name"]}
        for v in ids if v not in d["visited"]
    ]
    return {
        "hotel": {"name": prob.hotel_name,
                  "latitude": prob.hotel_lat, "longitude": prob.hotel_lon},
        "params": {"preference_text": preference_text, "budget": budget,
                   "n_days": n_days, "start_day": start_day,
                   "algorithm": algorithm,
                   "mode": "manual" if venue_ids else "otomatis"},
        "summary": {
            "fitness": round(float(res["best_fitness"]), 4),
            "n_candidates": len(ids),
            "n_visited": len(d["visited"]),
            "travel_total_min": round(d["travel_total"], 1),
            "cross_zone": d["cross_zone"],
            "zone_revisit": d["zone_revisit"],
            "zone_revisit_day": d["zone_revisit_day"],
            "violations": d["violations"],
        },
        "days": days_out,
        "not_fitted": not_fitted,
    }

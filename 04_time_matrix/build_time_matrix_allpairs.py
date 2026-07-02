"""
Hitung waktu tempuh semua kombinasi pasangan venue (all-pairs, tanpa batasan zone).
Dipakai GA/PSO untuk itinerary lintas zone â€” user bebas pilih venue dari manapun.

Berbeda dari build_time_matrix.py yang hanya hitung in-zone pairs.

Output: data/processed/jakarta_travel_time_allpairs.csv
    (venue_id_a, venue_id_b, duration_minutes, time_source)

Cache: sama dengan build_time_matrix.py (shared OSRM cache).
Resume-able: re-run lanjut dari pasangan yang belum dihitung.
"""
import itertools
import os
import sys
import time

import pandas as pd
import requests

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "01_data_collection"))
import config
from collect_osm import _haversine_m

TIME_MATRIX_ALLPAIRS_CSV = config.TIME_MATRIX_ALLPAIRS_CSV


def osrm_duration_minutes(lat1, lon1, lat2, lon2, timeout=10):
    url = f"{config.OSRM_BASE_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    try:
        resp = requests.get(url, params={"overview": "false"}, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("code") != "Ok":
            return None
        return data["routes"][0]["duration"] / 60.0
    except requests.RequestException:
        return None


def estimate_duration_minutes(lat1, lon1, lat2, lon2):
    dist_km = _haversine_m(lat1, lon1, lat2, lon2) / 1000.0
    return (dist_km / config.AVG_SPEED_KMH_FALLBACK) * 60.0


def main():
    df = pd.read_csv(config.CLUSTERED_VENUES_CSV)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])
    df = df.drop_duplicates(subset=["venue_id"])
    print(f"Venue input: {len(df)}")

    coord = df.set_index("venue_id")[["latitude", "longitude"]].astype(float)

    # Semua kombinasi pasangan (all-pairs, tanpa batasan zone)
    all_ids = df["venue_id"].tolist()
    pairs_to_compute = list(itertools.combinations(all_ids, 2))
    total_pairs = len(pairs_to_compute)
    print(f"Total pasangan all-pairs: {total_pairs}")

    # Load cache dari time_matrix_allpairs (resume-able)
    cache = {}
    if os.path.exists(TIME_MATRIX_ALLPAIRS_CSV):
        prev = pd.read_csv(TIME_MATRIX_ALLPAIRS_CSV)
        valid_keys = set(zip(prev.venue_id_a, prev.venue_id_b))
        valid_keys |= set(zip(prev.venue_id_b, prev.venue_id_a))
        for _, r in prev.iterrows():
            cache[(r["venue_id_a"], r["venue_id_b"])] = (r["duration_minutes"], r["time_source"])
        print(f"Cache ditemukan: {len(cache)} pasangan sudah dihitung.")
    else:
        # Seed cache dari time_matrix.csv (in-zone) â€” manfaatkan yang sudah ada
        if os.path.exists(config.TIME_MATRIX_CSV):
            inzone = pd.read_csv(config.TIME_MATRIX_CSV)
            for _, r in inzone.iterrows():
                cache[(r["venue_id_a"], r["venue_id_b"])] = (r["duration_minutes"], r["time_source"])
            print(f"Seed dari time_matrix in-zone: {len(cache)} pasangan.")

    os.makedirs(os.path.dirname(TIME_MATRIX_ALLPAIRS_CSV), exist_ok=True)

    rows = [{"venue_id_a": a, "venue_id_b": b, "duration_minutes": d, "time_source": s}
            for (a, b), (d, s) in cache.items()
            if tuple(sorted([a, b])) in {tuple(sorted(p)) for p in pairs_to_compute}]

    n_osrm, n_fallback, n_cached = 0, 0, len(rows)
    FLUSH_EVERY = 100

    for i, (a, b) in enumerate(pairs_to_compute):
        if (a, b) in cache or (b, a) in cache:
            continue
        lat1, lon1 = float(coord.loc[a, "latitude"]), float(coord.loc[a, "longitude"])
        lat2, lon2 = float(coord.loc[b, "latitude"]), float(coord.loc[b, "longitude"])
        dur = osrm_duration_minutes(lat1, lon1, lat2, lon2)
        if dur is not None:
            src = "osrm"
            n_osrm += 1
        else:
            dur = estimate_duration_minutes(lat1, lon1, lat2, lon2)
            src = "estimated"
            n_fallback += 1
        dur = round(dur, 1)
        rows.append({"venue_id_a": a, "venue_id_b": b,
                     "duration_minutes": dur, "time_source": src})
        cache[(a, b)] = (dur, src)
        time.sleep(0.5)

        new = n_osrm + n_fallback
        if new % FLUSH_EVERY == 0:
            pd.DataFrame(rows).to_csv(TIME_MATRIX_ALLPAIRS_CSV, index=False)
            pct = (n_cached + new) / total_pairs * 100
            print(f"  progress: {n_cached+new}/{total_pairs} ({pct:.1f}%) "
                  f"osrm={n_osrm} fallback={n_fallback} (saved)")

    out = pd.DataFrame(rows)
    out.to_csv(TIME_MATRIX_ALLPAIRS_CSV, index=False)
    total = len(out)
    print(f"\nSelesai: {total} pasangan")
    print(f"  dari cache/in-zone: {n_cached}")
    print(f"  OSRM baru: {n_osrm} ({n_osrm/max(total,1):.1%})")
    print(f"  fallback estimasi: {n_fallback} ({n_fallback/max(total,1):.1%})")
    print(f"Tersimpan -> {TIME_MATRIX_ALLPAIRS_CSV}")


if __name__ == "__main__":
    main()

"""
Hitung waktu tempuh antar venue (time matrix) -- beda dari time_spent (durasi
kunjungan DI venue). Dipakai sebagai constraint fitness GA/PSO (next phase,
belum dikerjakan di sini).

Scope dibatasi: hanya antar-venue dalam zone_id SAMA (bukan all-pairs se-Jakarta)
-- alasan teknis: OSRM public demo (router.project-osrm.org) ToS-limited,
bukan untuk produksi/bulk besar. Alasan logis: itinerary harian biasanya
antar venue berdekatan/zona sama.

Sumber waktu tempuh:
    1. OSRM (rute jalan asli, durasi detik dari response) -- utama
    2. Fallback haversine/avg_speed_kmh (estimasi, kalau OSRM gagal/timeout)
Kolom time_source menandai mana yang dipakai per pasangan.

Cache: hasil disimpan & dibaca ulang -- re-run tidak query OSRM utk pasangan
yang sudah pernah dihitung.

Output: data/processed/time_matrix.csv
    (venue_id_a, venue_id_b, duration_minutes, time_source)
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


def osrm_duration_minutes(lat1, lon1, lat2, lon2, timeout=10):
    """Panggil OSRM /route, return durasi menit. None kalau gagal."""
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
    """Fallback: haversine / avg_speed_kmh (estimasi kondisi macet Jakarta)."""
    dist_km = _haversine_m(lat1, lon1, lat2, lon2) / 1000.0
    return (dist_km / config.AVG_SPEED_KMH_FALLBACK) * 60.0


def main():
    df = pd.read_csv(config.CLUSTERED_VENUES_CSV)
    print(f"Venue input (clustered): {len(df)}")

    cache = {}
    if os.path.exists(config.TIME_MATRIX_CSV):
        prev = pd.read_csv(config.TIME_MATRIX_CSV)
        for _, r in prev.iterrows():
            cache[(r["venue_id_a"], r["venue_id_b"])] = (r["duration_minutes"], r["time_source"])
        print(f"Cache ditemukan: {len(cache)} pasangan sudah dihitung sebelumnya.")

    pairs_to_compute = []
    for zone in sorted(df["zone_id"].unique()):
        zone_df = df[df["zone_id"] == zone]
        ids = zone_df["venue_id"].tolist()
        pairs_to_compute.extend(itertools.combinations(ids, 2))

    print(f"Total pasangan dalam zone sama: {len(pairs_to_compute)}")

    os.makedirs(os.path.dirname(config.TIME_MATRIX_CSV), exist_ok=True)

    coord = df.set_index("venue_id")[["latitude", "longitude"]]
    rows = [{"venue_id_a": a, "venue_id_b": b, "duration_minutes": d, "time_source": s}
            for (a, b), (d, s) in cache.items()]
    n_osrm, n_fallback, n_cached = 0, 0, len(rows)
    FLUSH_EVERY = 50

    for i, (a, b) in enumerate(pairs_to_compute):
        key = (a, b)
        if key in cache or (b, a) in cache:
            continue  # sudah ada di rows lewat cache di atas
        lat1, lon1 = coord.loc[a]
        lat2, lon2 = coord.loc[b]
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
        cache[key] = (dur, src)
        time.sleep(0.5)  # jeda sopan, hindari rate-limit OSRM public demo

        if (n_osrm + n_fallback) % FLUSH_EVERY == 0:
            pd.DataFrame(rows).to_csv(config.TIME_MATRIX_CSV, index=False)
            done = n_osrm + n_fallback
            print(f"  progress: {done + n_cached}/{len(pairs_to_compute)} "
                  f"({i + 1}/{len(pairs_to_compute)} diproses, cache flushed)")

    out = pd.DataFrame(rows)
    total = len(out)
    print(f"\nSelesai: {total} pasangan")
    print(f"  dari cache (run sebelumnya): {n_cached}")
    print(f"  OSRM sukses: {n_osrm} ({n_osrm / max(total, 1):.1%})")
    print(f"  fallback estimasi: {n_fallback} ({n_fallback / max(total, 1):.1%})")

    out.to_csv(config.TIME_MATRIX_CSV, index=False)
    print(f"Tersimpan -> {config.TIME_MATRIX_CSV}")


if __name__ == "__main__":
    main()

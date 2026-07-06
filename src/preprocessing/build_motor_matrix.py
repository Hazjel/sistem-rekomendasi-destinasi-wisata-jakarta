"""
Matriks waktu tempuh MOTOR (rute non-tol) antar semua pasangan venue.

Motor dilarang masuk tol di Indonesia. OSRM profil 'bike'
(routing.openstreetmap.de/routed-bike) me-routing lewat jaringan jalan yang
menghindari motorway/tol -> jaraknya mewakili rute motor. Durasi bike terlalu
lambat (kecepatan sepeda), jadi yang dipakai = JARAK bike dibagi kecepatan
motor (config.MOTOR_SPEED_KMH).

Output: data/processed/jakarta_travel_time_motor.csv
  (venue_id_a, venue_id_b, distance_km, duration_minutes, time_source)

Cache-aware & resume-able: pasangan yang sudah tercatat di-skip, jadi bila
proses putus tinggal jalankan ulang. ~13rb pasangan, sleep 0.4s -> ~1.5-2 jam.

Jalankan dari root:
    python src/preprocessing/build_motor_matrix.py
"""
import itertools
import os
import sys
import time
from math import asin, cos, radians, sin, sqrt

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

SLEEP = 0.4  # jeda sopan antar request ke server publik


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def bike_distance_km(lat1, lon1, lat2, lon2, timeout=12):
    """Jarak rute non-tol (km) dari OSRM bike. None kalau gagal."""
    url = (f"{config.OSRM_BIKE_URL}/route/v1/driving/"
           f"{lon1},{lat1};{lon2},{lat2}")
    try:
        resp = requests.get(url, params={"overview": "false"}, timeout=timeout)
        data = resp.json()
        if data.get("code") != "Ok":
            return None
        return data["routes"][0]["distance"] / 1000.0
    except requests.RequestException:
        return None


def main():
    df = pd.read_csv(config.CLUSTERED_VENUES_CSV)
    df = df.dropna(subset=["latitude", "longitude"]).drop_duplicates("venue_id")
    coord = df.set_index("venue_id")[["latitude", "longitude"]].astype(float)
    pairs = list(itertools.combinations(df["venue_id"].tolist(), 2))
    print(f"Venue: {len(df)} | pasangan: {len(pairs)}")

    out_csv = config.TIME_MATRIX_MOTOR_CSV
    rows, done = [], set()
    if os.path.exists(out_csv):
        prev = pd.read_csv(out_csv)
        for _, r in prev.iterrows():
            done.add((r["venue_id_a"], r["venue_id_b"]))
            rows.append(r.to_dict())
        print(f"Cache: {len(done)} pasangan sudah ada, dilanjutkan.")

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    n_osrm = n_fb = 0
    for i, (a, b) in enumerate(pairs):
        if (a, b) in done or (b, a) in done:
            continue
        la1, lo1 = coord.loc[a]
        la2, lo2 = coord.loc[b]
        km = bike_distance_km(la1, lo1, la2, lo2)
        if km is not None:
            src = "osrm_bike"
            n_osrm += 1
        else:
            km = _haversine_km(la1, lo1, la2, lo2) * 1.3  # koreksi jalan berkelok
            src = "haversine"
            n_fb += 1
        dur = round((km / config.MOTOR_SPEED_KMH) * 60.0, 1)
        rows.append({"venue_id_a": a, "venue_id_b": b,
                     "distance_km": round(km, 2),
                     "duration_minutes": dur, "time_source": src})
        time.sleep(SLEEP)

        # simpan berkala (tahan putus)
        if (i + 1) % 200 == 0:
            pd.DataFrame(rows).to_csv(out_csv, index=False)
            print(f"  {i+1}/{len(pairs)} | osrm {n_osrm} fb {n_fb} "
                  f"| tersimpan {len(rows)}")

    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"Selesai: {len(rows)} pasangan -> {out_csv} "
          f"(osrm_bike {n_osrm}, fallback {n_fb})")


if __name__ == "__main__":
    main()

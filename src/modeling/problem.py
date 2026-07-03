"""
Formulasi TTDP (Tourist Trip Design Problem) — fondasi untuk GA/PSO/Hybrid.

Isi:
  - TTDPProblem: load dataset final + time matrix lookup + hotel
  - decode(): permutasi venue -> itinerary per hari (time-budget decoding)
  - fitness(): SUM satisfaction - penalti travel - penalti cross-zone - penalti jam

Decoding time-budget (representasi solusi = permutasi kandidat venue):
  Iterasi urutan venue; per hari akumulasi (travel + time_spent) mulai dari hotel.
  Venue yang melanggar budget harian / jam tutup -> dicoba hari berikutnya.
  Hari habis -> sisa venue tidak dikunjungi (tidak dihukum — satisfaction-nya
  saja yang hilang; ini standar Orienteering-style TTDP).

Semua parameter dari config.py (satu sumber untuk .py & notebook).
"""
import os
import sys
from math import radians, sin, cos, asin, sqrt

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _parse_hhmm(s):
    """'08:00' -> menit sejak 00:00. 'Tutup'/invalid -> None."""
    try:
        h, m = str(s).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


class TTDPProblem:
    """Instansiasi masalah: kandidat venue + hotel + hari kunjungan.

    Parameters
    ----------
    candidate_ids : list venue_id kandidat (hasil CBF top-N atau pilihan user)
    hotel : dict dgn latitude/longitude (row jakarta_hotels.csv) atau None ->
            default titik pusat Jakarta (Monas)
    n_days : jumlah hari itinerary
    start_day : nama hari pertama ('Senin'..'Minggu'); hari ke-i pakai jam buka
                hari kalender yang sesuai
    satisfaction : dict venue_id -> skor satisfaction (dari cbf.py). None ->
                   fallback rating-only.
    """

    def __init__(self, candidate_ids, hotel=None, n_days=2, start_day="Sabtu",
                 satisfaction=None,
                 day_start=config.DAY_START_MIN, day_end=config.DAY_END_MIN):
        self.venues = pd.read_csv(config.CLUSTERED_VENUES_CSV)
        self.venues = self.venues.set_index("venue_id", drop=False)
        missing = [v for v in candidate_ids if v not in self.venues.index]
        if missing:
            raise ValueError(f"venue_id tidak dikenal: {missing}")
        self.candidates = list(candidate_ids)
        self.n = len(self.candidates)
        self.n_days = n_days
        self.day_start = day_start
        self.day_end = day_end
        self.day_names = [DAYS_ID[(DAYS_ID.index(start_day) + i) % 7]
                          for i in range(n_days)]

        # Hotel start/end. Default: sekitar Monas (pusat kota).
        if hotel is None:
            self.hotel_lat, self.hotel_lon = -6.1754, 106.8272
            self.hotel_name = "(default: pusat kota)"
        else:
            self.hotel_lat = float(hotel["latitude"])
            self.hotel_lon = float(hotel["longitude"])
            self.hotel_name = hotel.get("name", "hotel")

        # Lookup travel time antar venue dari all-pairs matrix (menit).
        ap = pd.read_csv(config.TIME_MATRIX_ALLPAIRS_CSV)
        self._tt = {}
        for a, b, d in zip(ap["venue_id_a"], ap["venue_id_b"], ap["duration_minutes"]):
            self._tt[(a, b)] = d
            self._tt[(b, a)] = d

        # Pre-compute per kandidat: koordinat, zone, time_spent, jam buka per hari,
        # travel hotel<->venue (haversine/kecepatan rata2 — hotel tak ada di matrix).
        self._info = {}
        for vid in self.candidates:
            r = self.venues.loc[vid]
            hotel_min = (_haversine_km(self.hotel_lat, self.hotel_lon,
                                       r["latitude"], r["longitude"])
                         / config.AVG_SPEED_KMH_FALLBACK) * 60.0
            hours = {}
            for d in DAYS_ID:
                hours[d] = (_parse_hhmm(r.get(f"{d}_buka")),
                            _parse_hhmm(r.get(f"{d}_tutup")))
            self._info[vid] = {
                "zone": int(r["zone_id"]),
                "spent": float(r["time_spent_minutes"]),
                "hotel_min": hotel_min,
                "hours": hours,
                "name": r["name"],
            }

        # Satisfaction per kandidat. Fallback: rating ternormalisasi.
        if satisfaction is None:
            ratings = pd.to_numeric(
                self.venues.loc[self.candidates, "google_rating"],
                errors="coerce").fillna(0.0)
            lo, hi = ratings.min(), ratings.max()
            norm = (ratings - lo) / (hi - lo) if hi > lo else ratings * 0
            satisfaction = dict(zip(self.candidates, norm))
        self.satisfaction = dict(satisfaction)

    # ------------------------------------------------------------------
    def travel_min(self, a, b):
        """Waktu tempuh venue a -> b (menit). Fallback haversine kalau tak ada."""
        d = self._tt.get((a, b))
        if d is not None:
            return d
        ra, rb = self.venues.loc[a], self.venues.loc[b]
        km = _haversine_km(ra["latitude"], ra["longitude"],
                           rb["latitude"], rb["longitude"])
        return (km / config.AVG_SPEED_KMH_FALLBACK) * 60.0

    # ------------------------------------------------------------------
    def decode(self, perm):
        """Permutasi index kandidat -> itinerary.

        Returns dict:
          days        : list per hari -> list of visit dict
                        (venue_id, arrival, depart, wait, violation)
          visited     : set venue_id terkunjungi
          travel_total: menit perjalanan total (termasuk hotel legs)
          cross_zone  : jumlah perpindahan antar venue beda zona
          violations  : jumlah pelanggaran jam buka (soft — venue tetap
                        'dikunjungi' tapi kena penalti besar di fitness)
        """
        order = [self.candidates[i] for i in perm]
        days, visited = [], set()
        travel_total, cross_zone, violations = 0.0, 0, 0

        queue = list(order)
        for di in range(self.n_days):
            day_name = self.day_names[di]
            visits = []
            t = self.day_start
            prev = None      # None = masih di hotel
            leftover = []
            for vid in queue:
                info = self._info[vid]
                leg = info["hotel_min"] if prev is None else self.travel_min(prev, vid)
                arrive = t + leg
                open_m, close_m = info["hours"][day_name]
                if open_m is None or close_m is None:
                    leftover.append(vid)      # tutup hari ini -> coba hari lain
                    continue
                start_visit = max(arrive, open_m)  # tunggu kalau datang kepagian
                depart = start_visit + info["spent"]
                back = info["hotel_min"]
                # muat dalam budget hari? (harus sempat balik hotel)
                if depart + back > self.day_end:
                    leftover.append(vid)
                    continue
                violated = depart > close_m       # constraint TTDP (soft)
                visits.append({
                    "venue_id": vid, "name": info["name"],
                    "arrival": arrive, "start": start_visit, "depart": depart,
                    "violation": violated,
                })
                if violated:
                    violations += 1
                travel_total += leg
                if prev is not None and self._info[prev]["zone"] != info["zone"]:
                    cross_zone += 1
                visited.add(vid)
                prev, t = vid, depart
            if prev is not None:                  # balik hotel
                travel_total += self._info[prev]["hotel_min"]
            days.append(visits)
            queue = leftover
            if not queue:
                break

        return {"days": days, "visited": visited, "travel_total": travel_total,
                "cross_zone": cross_zone, "violations": violations}

    # ------------------------------------------------------------------
    def fitness(self, perm):
        """Skor fitness (maximize) untuk satu permutasi index kandidat."""
        d = self.decode(perm)
        sat = sum(self.satisfaction.get(v, 0.0) for v in d["visited"])
        return (sat
                - config.FITNESS_W_TIME * (d["travel_total"] / 60.0)
                - config.FITNESS_W_ZONE * d["cross_zone"]
                - config.FITNESS_PENALTY_HOURS * d["violations"])

    # ------------------------------------------------------------------
    def random_perm(self, rng):
        return rng.permutation(self.n)

    def zone_seeded_perm(self, rng):
        """Permutasi awal dikelompokkan per zona (inisialisasi cerdas —
        manfaatkan clustering; urutan zona & dalam-zona tetap diacak)."""
        by_zone = {}
        for i, vid in enumerate(self.candidates):
            by_zone.setdefault(self._info[vid]["zone"], []).append(i)
        zones = list(by_zone)
        rng.shuffle(zones)
        out = []
        for z in zones:
            idx = by_zone[z]
            rng.shuffle(idx)
            out.extend(idx)
        return np.array(out)

    def init_population(self, size, rng, zone_seed_frac=0.5):
        """Populasi awal: campuran random + zone-seeded."""
        pop = []
        n_seed = int(size * zone_seed_frac)
        for _ in range(n_seed):
            pop.append(self.zone_seeded_perm(rng))
        for _ in range(size - n_seed):
            pop.append(self.random_perm(rng))
        return pop


# ----------------------------------------------------------------------
def _sanity():
    """Cek cepat kewarasan decoding & fitness."""
    import json
    df = pd.read_csv(config.CLUSTERED_VENUES_CSV)
    # kandidat: 10 venue rating tertinggi
    top = df.sort_values("google_rating_count", ascending=False).head(10)
    prob = TTDPProblem(top["venue_id"].tolist(), n_days=2, start_day="Sabtu")

    rng = np.random.default_rng(config.RANDOM_SEED)
    perm = prob.random_perm(rng)
    d = prob.decode(perm)
    fit = prob.fitness(perm)
    print(f"Kandidat: {prob.n} | hari: {prob.n_days} ({prob.day_names})")
    print(f"Terkunjungi: {len(d['visited'])} | travel: {d['travel_total']:.0f} mnt "
          f"| cross-zone: {d['cross_zone']} | pelanggaran jam: {d['violations']}")
    print(f"Fitness: {fit:.3f}")
    for di, day in enumerate(d["days"]):
        print(f"  Hari {di+1} ({prob.day_names[di]}):")
        for v in day:
            mark = " [LANGGAR JAM]" if v["violation"] else ""
            print(f"    {v['name'][:40]:42s} "
                  f"{int(v['start'])//60:02d}:{int(v['start'])%60:02d}-"
                  f"{int(v['depart'])//60:02d}:{int(v['depart'])%60:02d}{mark}")

    # sanity: solusi zone-seeded harus >= random rata-rata (cek kasar)
    fits_r = [prob.fitness(prob.random_perm(rng)) for _ in range(20)]
    fits_z = [prob.fitness(prob.zone_seeded_perm(rng)) for _ in range(20)]
    print(f"\nMean fitness random      : {np.mean(fits_r):.3f}")
    print(f"Mean fitness zone-seeded : {np.mean(fits_z):.3f}")


if __name__ == "__main__":
    _sanity()

"""
Hyperparameter tuning — grid search per algoritma.

Desain fair-comparison:
  - Budget komputasi SAMA semua kombinasi (pop/particles=50, gen/iter=200)
  - Fitness function SAMA (tidak ikut di-tune — mengubahnya = mengubah metrik)
  - Diuji di 2 skenario ekstrem: 1hari_museum (12 kandidat, kecil) dan
    5hari_campuran (60 kandidat, besar) — parameter terbaik = rata-rata
    RANK antar skenario (bukan rata-rata fitness, skala beda)
  - 5 run per kombinasi (seed beda)

Fase A: grid GA (mut x cx) + grid PSO (w x c)
Fase B: grid Hybrid (refresh) memakai w/c terbaik hasil fase A

Output: data/processed/tuning_results.csv + print rekomendasi parameter.
"""
import os
import sys
import time
import itertools

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

from problem import TTDPProblem
from cbf import ContentBasedFilter
from ga import run_ga
from pso import run_pso
from hybrid import run_hybrid

TUNING_CSV = "data/processed/tuning_results.csv"
N_RUNS = 5

SCENARIOS = [
    ("1hari_museum",   1, "museum sejarah budaya",       "menengah"),
    ("5hari_campuran", 5, "museum taman pantai monumen", "menengah"),
]

GA_GRID = list(itertools.product([0.1, 0.2, 0.3], [0.7, 0.8, 0.9]))   # (mut, cx)
PSO_GRID = list(itertools.product([0.4, 0.5, 0.7], [1.0, 1.5, 2.0]))  # (w, c)
HYBRID_REFRESH = [5, 10, 20]


def _problems():
    cbf = ContentBasedFilter()
    out = []
    for label, n_days, pref, budget in SCENARIOS:
        ids, sat = cbf.candidates(n_days, pref, budget)
        out.append((label, TTDPProblem(ids, n_days=n_days, start_day="Sabtu",
                                       satisfaction=sat)))
    return out


def _eval(fn, prob, n_runs=N_RUNS, **kwargs):
    fits = []
    for r in range(n_runs):
        res = fn(prob, seed=config.RANDOM_SEED + r, **kwargs)
        fits.append(res["best_fitness"])
    return float(np.mean(fits)), float(np.std(fits))


def main():
    probs = _problems()
    rows = []

    # --- Fase A: GA grid ---
    print(f"=== GA grid: {len(GA_GRID)} kombinasi x {len(probs)} skenario x {N_RUNS} run ===")
    for mut, cx in GA_GRID:
        for label, prob in probs:
            t0 = time.perf_counter()
            mean, std = _eval(run_ga, prob, mut_rate=mut, cx_rate=cx)
            rows.append({"algorithm": "GA", "params": f"mut={mut},cx={cx}",
                         "mut": mut, "cx": cx, "w": None, "c": None, "refresh": None,
                         "scenario": label, "fitness_mean": mean, "fitness_std": std,
                         "sec": round(time.perf_counter() - t0, 1)})
        print(f"  mut={mut} cx={cx}: "
              + " | ".join(f"{r['scenario']}={r['fitness_mean']:.2f}"
                           for r in rows[-len(probs):]))

    # --- Fase A: PSO grid ---
    print(f"\n=== PSO grid: {len(PSO_GRID)} kombinasi ===")
    for w, c in PSO_GRID:
        for label, prob in probs:
            t0 = time.perf_counter()
            mean, std = _eval(run_pso, prob, w=w, c1=c, c2=c)
            rows.append({"algorithm": "PSO", "params": f"w={w},c={c}",
                         "mut": None, "cx": None, "w": w, "c": c, "refresh": None,
                         "scenario": label, "fitness_mean": mean, "fitness_std": std,
                         "sec": round(time.perf_counter() - t0, 1)})
        print(f"  w={w} c={c}: "
              + " | ".join(f"{r['scenario']}={r['fitness_mean']:.2f}"
                           for r in rows[-len(probs):]))

    df = pd.DataFrame(rows)

    # Parameter terbaik = mean rank antar skenario (robust thd beda skala fitness)
    def best_by_rank(sub):
        sub = sub.copy()
        sub["rank"] = sub.groupby("scenario")["fitness_mean"].rank(ascending=False)
        agg = sub.groupby("params")["rank"].mean().sort_values()
        return agg.index[0], agg

    ga_best, ga_ranks = best_by_rank(df[df.algorithm == "GA"])
    pso_best, pso_ranks = best_by_rank(df[df.algorithm == "PSO"])
    pso_best_row = df[(df.algorithm == "PSO") & (df.params == pso_best)].iloc[0]
    w_best, c_best = float(pso_best_row["w"]), float(pso_best_row["c"])

    # --- Fase B: Hybrid grid (pakai w/c terbaik PSO) ---
    print(f"\n=== Hybrid grid: refresh {HYBRID_REFRESH} (pakai w={w_best}, c={c_best}) ===")
    for rf in HYBRID_REFRESH:
        for label, prob in probs:
            t0 = time.perf_counter()
            mean, std = _eval(run_hybrid, prob, refresh_every=rf,
                              w=w_best, c1=c_best, c2=c_best)
            rows.append({"algorithm": "Hybrid", "params": f"refresh={rf},w={w_best},c={c_best}",
                         "mut": None, "cx": None, "w": w_best, "c": c_best, "refresh": rf,
                         "scenario": label, "fitness_mean": mean, "fitness_std": std,
                         "sec": round(time.perf_counter() - t0, 1)})
        print(f"  refresh={rf}: "
              + " | ".join(f"{r['scenario']}={r['fitness_mean']:.2f}"
                           for r in rows[-len(probs):]))

    df = pd.DataFrame(rows)
    hy_best, hy_ranks = best_by_rank(df[df.algorithm == "Hybrid"])

    df.to_csv(TUNING_CSV, index=False)
    print(f"\nTersimpan -> {TUNING_CSV}")
    print("\n=== REKOMENDASI PARAMETER (mean rank lintas skenario) ===")
    print(f"GA     : {ga_best}")
    print(f"PSO    : {pso_best}")
    print(f"Hybrid : {hy_best}")
    print("\nDetail rank GA:");     print(ga_ranks.to_string())
    print("\nDetail rank PSO:");    print(pso_ranks.to_string())
    print("\nDetail rank Hybrid:"); print(hy_ranks.to_string())


if __name__ == "__main__":
    main()

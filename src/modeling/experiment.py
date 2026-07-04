"""
Runner eksperimen: GA vs PSO vs GA-PSO Hybrid untuk paper.

Tiap skenario x algoritma dijalankan EXPERIMENT_N_RUNS kali (seed beda) —
mencatat: fitness akhir, venue terkunjungi, travel time, pelanggaran jam,
User Satisfaction Score (USS), runtime, dan kurva konvergensi.

USS (kuantitatif, tujuan #5 slide):
  USS = SUM satisfaction(venue terkunjungi) / SUM satisfaction(top-K ideal)
  K = jumlah venue terkunjungi -> rasio 0-1 terhadap "keinginan maksimal"
  turis bila bisa mengunjungi venue terbaik tanpa constraint ruang-waktu.

Output:
  data/processed/optimization_results.csv      (1 row per run)
  data/processed/optimization_convergence.csv  (long format utk kurva)
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

from problem import TTDPProblem
from cbf import ContentBasedFilter
from ga import run_ga
from pso import run_pso
from hybrid import run_hybrid

ALGOS = {"GA": run_ga, "PSO": run_pso, "Hybrid": run_hybrid}

# Skenario uji: (label, n_days, preferensi, budget)
SCENARIOS = [
    ("1hari_museum",  1, "museum sejarah budaya",        "menengah"),
    ("3hari_keluarga", 3, "theme park zoo aquarium",      "bebas"),
    ("5hari_campuran", 5, "museum taman pantai monumen",  "menengah"),
]


def uss(problem, visited):
    """User Satisfaction Score: rasio thd top-K kandidat ideal."""
    if not visited:
        return 0.0
    got = sum(problem.satisfaction.get(v, 0.0) for v in visited)
    ideal = sorted(problem.satisfaction.values(), reverse=True)[: len(visited)]
    denom = sum(ideal)
    return got / denom if denom > 0 else 0.0


def run_experiments(n_runs=config.EXPERIMENT_N_RUNS, scenarios=SCENARIOS,
                    verbose=True):
    cbf = ContentBasedFilter()
    results, convergence = [], []

    for label, n_days, pref, budget in scenarios:
        ids, sat = cbf.candidates(n_days, pref, budget)
        prob = TTDPProblem(ids, n_days=n_days, start_day="Sabtu",
                           satisfaction=sat)
        if verbose:
            print(f"\n=== Skenario {label}: {prob.n} kandidat, {n_days} hari ===")
        for algo_name, algo_fn in ALGOS.items():
            for run in range(n_runs):
                seed = config.RANDOM_SEED + run
                t0 = time.perf_counter()
                res = algo_fn(prob, seed=seed)
                dt = time.perf_counter() - t0
                d = prob.decode(res["best_perm"])
                results.append({
                    "scenario": label, "algorithm": algo_name, "run": run,
                    "seed": seed, "fitness": res["best_fitness"],
                    "n_visited": len(d["visited"]),
                    "travel_min": round(d["travel_total"], 1),
                    "cross_zone": d["cross_zone"],
                    "zone_revisit": d["zone_revisit"],
                    "zone_revisit_day": d["zone_revisit_day"],
                    "violations": d["violations"],
                    "uss": round(uss(prob, d["visited"]), 4),
                    "runtime_sec": round(dt, 2),
                })
                for gen, f in enumerate(res["history"]):
                    convergence.append({
                        "scenario": label, "algorithm": algo_name,
                        "run": run, "generation": gen, "best_fitness": f,
                    })
            if verbose:
                sub = [r for r in results
                       if r["scenario"] == label and r["algorithm"] == algo_name]
                fits = [r["fitness"] for r in sub]
                print(f"  {algo_name:7s}: fitness {np.mean(fits):.3f} ± "
                      f"{np.std(fits):.3f} | USS {np.mean([r['uss'] for r in sub]):.3f}"
                      f" | viol {np.mean([r['violations'] for r in sub]):.1f}"
                      f" | {np.mean([r['runtime_sec'] for r in sub]):.1f}s/run")

    res_df = pd.DataFrame(results)
    conv_df = pd.DataFrame(convergence)
    res_df.to_csv(config.EXPERIMENT_RESULTS_CSV, index=False)
    conv_df.to_csv(config.CONVERGENCE_LOG_CSV, index=False)
    if verbose:
        print(f"\nTersimpan -> {config.EXPERIMENT_RESULTS_CSV}")
        print(f"Tersimpan -> {config.CONVERGENCE_LOG_CSV}")
    return res_df, conv_df


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=config.EXPERIMENT_N_RUNS)
    ap.add_argument("--quick", action="store_true",
                    help="uji cepat: 2 run, skenario pertama saja")
    args = ap.parse_args()
    if args.quick:
        run_experiments(n_runs=2, scenarios=SCENARIOS[:1])
    else:
        run_experiments(n_runs=args.runs)

"""
Runner eksperimen: 7 algoritma (GA, PSO, Hybrid, GWO-TS, ACO-SA, WOA-ILS,
GRASP-ABC) untuk paper — sama seperti Tabel I JADIMI. 3 algoritma terakhir
adalah port dari kode rekan (notebook eksternal, representasi zona-toy
4-slot/hari) ke representasi permutasi TTDPProblem yang dipakai algoritma
lain di modul ini (lihat docstring aco_sa.py / woa_ils.py / grasp_abc.py).

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
import multiprocessing as mp

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

from problem import TTDPProblem
from cbf import ContentBasedFilter
from ga import run_ga
from pso import run_pso
from hybrid import run_hybrid
from gwo_ts import run_gwo_ts
from aco_sa import run_aco_sa
from woa_ils import run_woa_ils
from grasp_abc import run_grasp_abc

ALGOS = {"GA": run_ga, "PSO": run_pso, "Hybrid": run_hybrid,
         "GWO-TS": run_gwo_ts, "ACO-SA": run_aco_sa,
         "WOA-ILS": run_woa_ils, "GRASP-ABC": run_grasp_abc}

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


def _run_one(problem, algo_name, run):
    """Satu (algoritma, run) pada satu problem sudah-dibangun. Returns
    (result_row, convergence_rows). Sama persis dgn badan loop sekuensial —
    dipakai baik oleh run_experiments() maupun worker paralel, sehingga
    ANGKA HASIL identik terlepas dari mode eksekusi (seed = RANDOM_SEED+run
    tidak bergantung urutan/proses)."""
    algo_fn = ALGOS[algo_name]
    seed = config.RANDOM_SEED + run
    t0 = time.perf_counter()
    res = algo_fn(problem, seed=seed)
    dt = time.perf_counter() - t0
    d = problem.decode(res["best_perm"])
    row = {
        "scenario": problem._label, "algorithm": algo_name, "run": run,
        "seed": seed, "fitness": res["best_fitness"],
        "n_visited": len(d["visited"]),
        "travel_min": round(d["travel_total"], 1),
        "cross_zone": d["cross_zone"],
        "zone_revisit": d["zone_revisit"],
        "zone_revisit_day": d["zone_revisit_day"],
        "violations": d["violations"],
        "uss": round(uss(problem, d["visited"]), 4),
        "runtime_sec": round(dt, 2),
    }
    conv_rows = [{"scenario": problem._label, "algorithm": algo_name,
                 "run": run, "generation": gen, "best_fitness": f}
                for gen, f in enumerate(res["history"])]
    return row, conv_rows


# --- Eksekusi paralel (multiprocessing) --------------------------------
# Tiap worker membangun SEMUA TTDPProblem sekali (mahal: baca CSV + hitung
# travel time antar kandidat) lalu memproses banyak task (scenario, algo,
# run) tanpa membangun ulang. Task didistribusi granular per-run (bukan
# per-algoritma) supaya beban antar worker rata — GRASP-ABC/WOA-ILS jauh
# lebih berat dari GA/PSO, kalau dikelompokkan per-algoritma sebagian
# worker akan menganggur sementara worker lain kebagian algoritma berat.
_worker_problems = None


def _init_worker(scenarios):
    global _worker_problems
    cbf = ContentBasedFilter()
    _worker_problems = {}
    for label, n_days, pref, budget in scenarios:
        ids, sat = cbf.candidates(n_days, pref, budget)
        prob = TTDPProblem(ids, n_days=n_days, start_day="Sabtu", satisfaction=sat)
        prob._label = label
        _worker_problems[label] = prob


def _worker_task(task):
    label, algo_name, run = task
    return _run_one(_worker_problems[label], algo_name, run)


def run_experiments_parallel(n_runs=config.EXPERIMENT_N_RUNS, scenarios=SCENARIOS,
                             n_workers=None, verbose=True):
    """Sama persis dgn run_experiments() (angka hasil identik — seed
    per-run tidak bergantung proses), tapi task (scenario, algoritma, run)
    didistribusi ke banyak proses CPU. Cocok karena tiap task independen
    (tidak ada state acak yang dibagi antar run)."""
    n_workers = n_workers or max(1, (os.cpu_count() or 4) - 2)
    tasks = [(label, algo_name, run)
            for label, *_ in scenarios
            for algo_name in ALGOS
            for run in range(n_runs)]

    if verbose:
        print(f"=== Paralel: {len(tasks)} task ({len(scenarios)} skenario x "
              f"{len(ALGOS)} algoritma x {n_runs} run) di {n_workers} proses ===")

    results, convergence = [], []
    t_start = time.perf_counter()
    with mp.Pool(n_workers, initializer=_init_worker,
                initargs=(scenarios,)) as pool:
        for i, (row, conv_rows) in enumerate(
                pool.imap_unordered(_worker_task, tasks), start=1):
            results.append(row)
            convergence.extend(conv_rows)
            if verbose and i % 50 == 0:
                elapsed = time.perf_counter() - t_start
                rate = i / elapsed
                eta = (len(tasks) - i) / rate if rate > 0 else float("inf")
                print(f"  {i}/{len(tasks)} task selesai "
                      f"({elapsed:.0f}s berlalu, ETA {eta:.0f}s)")

    res_df = pd.DataFrame(results)
    order = {label: k for k, (label, *_) in enumerate(scenarios)}
    res_df["_so"] = res_df["scenario"].map(order)
    res_df["_ao"] = res_df["algorithm"].map({a: k for k, a in enumerate(ALGOS)})
    res_df = (res_df.sort_values(["_so", "_ao", "run"])
             .drop(columns=["_so", "_ao"]).reset_index(drop=True))
    conv_df = pd.DataFrame(convergence)

    res_df.to_csv(config.EXPERIMENT_RESULTS_CSV, index=False)
    conv_df.to_csv(config.CONVERGENCE_LOG_CSV, index=False)
    if verbose:
        total = time.perf_counter() - t_start
        print(f"\nSelesai dalam {total:.0f}s ({total/60:.1f} menit)")
        print(f"Tersimpan -> {config.EXPERIMENT_RESULTS_CSV}")
        print(f"Tersimpan -> {config.CONVERGENCE_LOG_CSV}")
        for label, *_ in scenarios:
            sub = res_df[res_df["scenario"] == label]
            print(f"\n=== {label} ===")
            for algo_name in ALGOS:
                a = sub[sub["algorithm"] == algo_name]
                print(f"  {algo_name:10s}: fitness {a['fitness'].mean():.3f} ± "
                      f"{a['fitness'].std():.3f} | USS {a['uss'].mean():.3f}"
                      f" | viol {a['violations'].mean():.1f}"
                      f" | {a['runtime_sec'].mean():.1f}s/run")
    return res_df, conv_df


def run_experiments(n_runs=config.EXPERIMENT_N_RUNS, scenarios=SCENARIOS,
                    verbose=True):
    """Mode sekuensial (1 proses). Badan loop memakai _run_one() — fungsi
    yang sama dipakai worker paralel, jadi angka hasil dijamin identik
    dengan run_experiments_parallel() untuk seed yang sama."""
    cbf = ContentBasedFilter()
    results, convergence = [], []

    for label, n_days, pref, budget in scenarios:
        ids, sat = cbf.candidates(n_days, pref, budget)
        prob = TTDPProblem(ids, n_days=n_days, start_day="Sabtu",
                           satisfaction=sat)
        prob._label = label
        if verbose:
            print(f"\n=== Skenario {label}: {prob.n} kandidat, {n_days} hari ===")
        for algo_name in ALGOS:
            for run in range(n_runs):
                row, conv_rows = _run_one(prob, algo_name, run)
                results.append(row)
                convergence.extend(conv_rows)
            if verbose:
                sub = [r for r in results
                       if r["scenario"] == label and r["algorithm"] == algo_name]
                fits = [r["fitness"] for r in sub]
                print(f"  {algo_name:10s}: fitness {np.mean(fits):.3f} ± "
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
    ap.add_argument("--parallel", action="store_true",
                    help="distribusi task (scenario,algoritma,run) ke banyak "
                         "proses CPU. Angka hasil identik dgn mode sekuensial "
                         "(seed per-run tidak bergantung proses) — cuma lebih cepat.")
    ap.add_argument("--workers", type=int, default=None,
                    help="jumlah proses paralel (default: cpu_count - 2)")
    args = ap.parse_args()
    if args.quick:
        scenarios, runs = SCENARIOS[:1], 2
    else:
        scenarios, runs = SCENARIOS, args.runs

    if args.parallel:
        run_experiments_parallel(n_runs=runs, scenarios=scenarios,
                                 n_workers=args.workers)
    else:
        run_experiments(n_runs=runs, scenarios=scenarios)

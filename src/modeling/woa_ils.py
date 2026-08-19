"""
WOA-ILS Hybrid (Whale Optimization Algorithm + Iterated Local Search) TTDP.

Port dari notebook WOA-ILS rekan ke representasi permutasi TTDPProblem —
sama seperti gwo_ts.py:

  WOA (pencarian global — populasi 'paus'):
    - a turun linear 2 -> 0 (identik GWO). A = 2*a*r1 - a mengatur
      eksploitasi/eksplorasi; p ~ U(0,1) memilih manuver:
        p < 0.5  -> PENGEPUNGAN: |A|<1 berenang mendekati gbest (swap-sequence
                    prob 0.6), |A|>=1 menjauh ke paus acak (prob 0.5).
        p >= 0.5 -> SPIRAL: mendekati gbest dgn swap-sequence prob 0.3,
                    diselingi swap-mutation acak (prob 0.2) — spiral kontinu
                    notebook diterjemahkan sbg gerak menuju-gbest + noise,
                    konsisten dgn adaptasi swap-sequence GWO-TS.
      (koefisien C notebook dihitung tapi tidak dipakai di manuvernya sendiri
      — dipertahankan tidak dipakai di sini juga, demi kesetiaan port.)

  ILS (intensifikasi gbest tiap iterasi — analog TS di GWO-TS):
    - Perturbation: 2x swap-mutation acak.
    - Local search: 2-opt (local_search.two_opt, dibatasi WOA_ILS_MAX_PASS
      karena dipanggil TIAP iterasi, beda dari GA/PSO yang cuma sekali di
      akhir run).
    Elitism: whale 0 dipaksa diam di gbest hasil ILS (identik pola wolf 0
    di GWO-TS).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

from ga import swap_mutation
from pso import swap_sequence
from local_search import two_opt


def _apply_swaps_prob(perm, swaps, prob, rng):
    """Terapkan tiap swap dengan probabilitas `prob` (semantik apply_swaps
    notebook — sama dengan gwo_ts._apply_swaps_prob)."""
    p = perm.copy()
    for i, j in swaps:
        if rng.random() < prob:
            p[i], p[j] = p[j], p[i]
    return p


def iterated_local_search(problem, perm, rng, max_pass=config.WOA_ILS_MAX_PASS):
    """Perturbation (2x swap-mutation) + 2-opt. Returns (perm, fitness)."""
    p = swap_mutation(perm, rng)
    p = swap_mutation(p, rng)
    return two_opt(problem, p, max_pass=max_pass)


def run_woa_ils(problem, seed=config.RANDOM_SEED,
                n_whales=config.WOA_N_WHALES, n_iter=config.WOA_N_ITER,
                verbose=False):
    """Returns dict: best_perm, best_fitness, history (best fitness/iterasi)."""
    rng = np.random.default_rng(seed)
    whales = problem.init_population(n_whales, rng)
    fits = [problem.fitness(w) for w in whales]

    gi = int(np.argmax(fits))
    gbest, gbest_fit = whales[gi].copy(), fits[gi]
    history = []

    for it in range(n_iter):
        a = 2.0 - it * (2.0 / n_iter)

        for i in range(n_whales):
            w = whales[i].copy()
            r1, r2 = rng.random(), rng.random()
            A = 2 * a * r1 - a
            p = rng.random()

            if p < 0.5:
                if abs(A) < 1.0:
                    swaps = swap_sequence(w, gbest)
                    w = _apply_swaps_prob(w, swaps, 0.6, rng)
                else:
                    rand_whale = whales[int(rng.integers(n_whales))]
                    swaps = swap_sequence(w, rand_whale)
                    w = _apply_swaps_prob(w, swaps, 0.5, rng)
            else:
                swaps = swap_sequence(w, gbest)
                w = _apply_swaps_prob(w, swaps, 0.3, rng)
                if rng.random() < 0.2:
                    w = swap_mutation(w, rng)

            whales[i] = w

        fits = [problem.fitness(w) for w in whales]
        gi = int(np.argmax(fits))
        if fits[gi] > gbest_fit:
            gbest, gbest_fit = whales[gi].copy(), fits[gi]

        # suntikan ILS pada gbest
        refined, refined_fit = iterated_local_search(problem, gbest, rng)
        if refined_fit > gbest_fit:
            gbest, gbest_fit = refined.copy(), refined_fit
            whales[0] = gbest.copy()      # elitism

        history.append(gbest_fit)
        if verbose and (it + 1) % 20 == 0:
            print(f"  iter {it+1:4d}: gbest={gbest_fit:.4f}")

    return {"best_perm": gbest, "best_fitness": gbest_fit, "history": history}


if __name__ == "__main__":
    from problem import TTDPProblem
    from cbf import ContentBasedFilter

    cbf = ContentBasedFilter()
    ids, sat = cbf.candidates(2, "museum sejarah budaya", "menengah")
    prob = TTDPProblem(ids, n_days=2, start_day="Sabtu", satisfaction=sat)
    print(f"Kandidat: {prob.n} | WOA-ILS whales={config.WOA_N_WHALES} "
          f"iter={config.WOA_N_ITER}")
    res = run_woa_ils(prob, verbose=True)
    print(f"\nBest fitness: {res['best_fitness']:.4f}")
    print(f"gbest iter-1 vs akhir: {res['history'][0]:.4f} -> {res['history'][-1]:.4f}")
    d = prob.decode(res["best_perm"])
    print(f"Terkunjungi {len(d['visited'])} | travel {d['travel_total']:.0f} mnt "
          f"| cross-zone {d['cross_zone']} | pelanggaran {d['violations']}")

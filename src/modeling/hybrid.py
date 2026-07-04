"""
GA-PSO Hybrid untuk TTDP.

Skema umum literatur hybrid metaheuristic: PSO sebagai kerangka utama
(pbest/gbest memandu eksplorasi), tiap HYBRID_GA_REFRESH_EVERY iterasi
populasi di-refresh dengan operator genetik:
  - separuh partikel terburuk diganti hasil OX-crossover (pbest x gbest)
    + swap mutation
  -> menyuntik diversitas & memperbaiki kelemahan PSO diskrit yang mudah
     stagnan di ruang permutasi.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

from ga import order_crossover, swap_mutation
from local_search import two_opt
from pso import swap_sequence, apply_swaps


def run_hybrid(problem, seed=config.RANDOM_SEED,
               n_particles=config.PSO_N_PARTICLES, n_iter=config.PSO_N_ITER,
               w=config.PSO_W, c1=config.PSO_C1, c2=config.PSO_C2,
               refresh_every=config.HYBRID_GA_REFRESH_EVERY,
               mut_rate=config.GA_MUTATION_RATE,
               verbose=False, polish=True):
    """Returns dict: best_perm, best_fitness, history.

    polish=True: gbest akhir dirapikan 2-opt local search."""
    rng = np.random.default_rng(seed)
    X = problem.init_population(n_particles, rng)
    V = [[] for _ in range(n_particles)]
    fits = [problem.fitness(x) for x in X]

    pbest = [x.copy() for x in X]
    pbest_fit = list(fits)
    gi = int(np.argmax(fits))
    gbest, gbest_fit = X[gi].copy(), fits[gi]
    history = []

    for it in range(n_iter):
        # --- langkah PSO standar ---
        for i in range(n_particles):
            v_new = [s for s in V[i] if rng.random() < w]
            for s in swap_sequence(X[i], pbest[i]):
                if rng.random() < min(1.0, c1 * rng.random()):
                    v_new.append(s)
            for s in swap_sequence(X[i], gbest):
                if rng.random() < min(1.0, c2 * rng.random()):
                    v_new.append(s)
            X[i] = apply_swaps(X[i], v_new)
            V[i] = v_new

            f = problem.fitness(X[i])
            if f > pbest_fit[i]:
                pbest[i], pbest_fit[i] = X[i].copy(), f
            if f > gbest_fit:
                gbest, gbest_fit = X[i].copy(), f

        # --- refresh genetik: ganti separuh terburuk ---
        if (it + 1) % refresh_every == 0:
            cur_fits = [problem.fitness(x) for x in X]
            worst = np.argsort(cur_fits)[: n_particles // 2]
            for i in worst:
                child = order_crossover(pbest[i], gbest, rng)
                if rng.random() < mut_rate:
                    child = swap_mutation(child, rng)
                X[i] = child
                V[i] = []
                f = problem.fitness(child)
                if f > pbest_fit[i]:
                    pbest[i], pbest_fit[i] = child.copy(), f
                if f > gbest_fit:
                    gbest, gbest_fit = child.copy(), f

        history.append(gbest_fit)
        if verbose and (it + 1) % 50 == 0:
            print(f"  iter {it+1:4d}: gbest={gbest_fit:.4f}")

    if polish:
        pre = gbest_fit
        gbest, gbest_fit = two_opt(problem, gbest)
        if verbose:
            print(f"  2-opt polish: {pre:.4f} -> {gbest_fit:.4f}")
        history.append(gbest_fit)
    return {"best_perm": gbest, "best_fitness": gbest_fit, "history": history}


if __name__ == "__main__":
    from problem import TTDPProblem
    from cbf import ContentBasedFilter

    cbf = ContentBasedFilter()
    ids, sat = cbf.candidates(2, "museum sejarah budaya", "menengah")
    prob = TTDPProblem(ids, n_days=2, start_day="Sabtu", satisfaction=sat)
    print(f"Kandidat: {prob.n} | Hybrid particles={config.PSO_N_PARTICLES} "
          f"iter={config.PSO_N_ITER} refresh tiap {config.HYBRID_GA_REFRESH_EVERY}")
    res = run_hybrid(prob, verbose=True)
    print(f"\nBest fitness: {res['best_fitness']:.4f}")
    d = prob.decode(res["best_perm"])
    print(f"Terkunjungi {len(d['visited'])} | travel {d['travel_total']:.0f} mnt "
          f"| cross-zone {d['cross_zone']} | pelanggaran {d['violations']}")

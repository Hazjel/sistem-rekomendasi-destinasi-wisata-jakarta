"""
PSO diskrit untuk TTDP (permutasi) — pendekatan swap-sequence.

Adaptasi PSO kontinu ke ruang permutasi (Wang et al. 2003, umum utk TSP-like):
  - Posisi partikel = permutasi index kandidat
  - Velocity = daftar swap (i, j) yang mentransformasi permutasi
  - v(t+1) = w*v(t) + c1*r1*(pbest - x) + c2*r2*(gbest - x)
    * (pbest - x) = swap-sequence yang mengubah x menjadi pbest
    * koefisien dipakai sebagai probabilitas mempertahankan tiap swap
  - x(t+1) = x(t) + v(t+1)  (apply swap berurutan)
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

from local_search import two_opt


def swap_sequence(from_perm, to_perm):
    """Daftar swap (i, j) minimal yang mengubah from_perm -> to_perm."""
    p = from_perm.copy()
    pos = {g: i for i, g in enumerate(p)}
    swaps = []
    for i in range(len(p)):
        if p[i] != to_perm[i]:
            j = pos[to_perm[i]]
            swaps.append((i, j))
            pos[p[i]], pos[p[j]] = j, i
            p[i], p[j] = p[j], p[i]
    return swaps


def apply_swaps(perm, swaps):
    p = perm.copy()
    for i, j in swaps:
        p[i], p[j] = p[j], p[i]
    return p


def run_pso(problem, seed=config.RANDOM_SEED,
            n_particles=config.PSO_N_PARTICLES, n_iter=config.PSO_N_ITER,
            w=config.PSO_W, c1=config.PSO_C1, c2=config.PSO_C2,
            verbose=False, polish=True):
    """Returns dict: best_perm, best_fitness, history.

    polish=True: gbest akhir dirapikan 2-opt local search."""
    rng = np.random.default_rng(seed)
    X = problem.init_population(n_particles, rng)
    V = [[] for _ in range(n_particles)]            # velocity awal kosong
    fits = [problem.fitness(x) for x in X]

    pbest = [x.copy() for x in X]
    pbest_fit = list(fits)
    gi = int(np.argmax(fits))
    gbest, gbest_fit = X[gi].copy(), fits[gi]
    history = []

    for it in range(n_iter):
        for i in range(n_particles):
            # inertia: pertahankan tiap swap lama dengan prob. w
            v_new = [s for s in V[i] if rng.random() < w]
            # kognitif: swap menuju pbest, tiap swap dgn prob. c1*r1 (clip 1)
            for s in swap_sequence(X[i], pbest[i]):
                if rng.random() < min(1.0, c1 * rng.random()):
                    v_new.append(s)
            # sosial: swap menuju gbest
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
    print(f"Kandidat: {prob.n} | PSO particles={config.PSO_N_PARTICLES} "
          f"iter={config.PSO_N_ITER}")
    res = run_pso(prob, verbose=True)
    print(f"\nBest fitness: {res['best_fitness']:.4f}")
    print(f"gbest iter-1 vs akhir: {res['history'][0]:.4f} -> {res['history'][-1]:.4f}")
    d = prob.decode(res["best_perm"])
    print(f"Terkunjungi {len(d['visited'])} | travel {d['travel_total']:.0f} mnt "
          f"| cross-zone {d['cross_zone']} | pelanggaran {d['violations']}")

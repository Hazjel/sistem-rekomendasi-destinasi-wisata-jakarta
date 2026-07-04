"""
Genetic Algorithm untuk TTDP (permutasi kandidat venue).

Operator (manual numpy — transparan untuk paper):
  - Seleksi  : tournament (k dari config.GA_TOURNAMENT_K)
  - Crossover: Order Crossover / OX (mempertahankan sifat permutasi)
  - Mutasi   : swap dua posisi acak
  - Elitism  : GA_ELITE individu terbaik lolos langsung ke generasi berikut

Representasi = permutasi index kandidat (lihat problem.TTDPProblem.decode).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

from local_search import two_opt


def order_crossover(p1, p2, rng):
    """OX: salin segmen acak dari p1, sisanya diisi urutan gen p2."""
    n = len(p1)
    a, b = sorted(rng.integers(0, n, size=2))
    child = np.full(n, -1)
    child[a:b + 1] = p1[a:b + 1]
    used = set(child[a:b + 1])
    fill = [g for g in p2 if g not in used]
    j = 0
    for i in range(n):
        if child[i] == -1:
            child[i] = fill[j]
            j += 1
    return child


def swap_mutation(perm, rng):
    p = perm.copy()
    i, j = rng.integers(0, len(p), size=2)
    p[i], p[j] = p[j], p[i]
    return p


def tournament(pop, fits, k, rng):
    idx = rng.integers(0, len(pop), size=k)
    best = idx[np.argmax([fits[i] for i in idx])]
    return pop[best]


def run_ga(problem, seed=config.RANDOM_SEED,
           pop_size=config.GA_POP_SIZE, n_gen=config.GA_N_GEN,
           cx_rate=config.GA_CROSSOVER_RATE, mut_rate=config.GA_MUTATION_RATE,
           tournament_k=config.GA_TOURNAMENT_K, n_elite=config.GA_ELITE,
           verbose=False, polish=True):
    """Returns dict: best_perm, best_fitness, history (best fitness/generasi).

    polish=True: solusi akhir dirapikan 2-opt local search (hapus pola
    bolak-balik lokal yang lolos dari operator GA)."""
    rng = np.random.default_rng(seed)
    pop = problem.init_population(pop_size, rng)
    fits = [problem.fitness(p) for p in pop]
    history = []

    for gen in range(n_gen):
        order = np.argsort(fits)[::-1]
        new_pop = [pop[i].copy() for i in order[:n_elite]]     # elitism
        while len(new_pop) < pop_size:
            p1 = tournament(pop, fits, tournament_k, rng)
            p2 = tournament(pop, fits, tournament_k, rng)
            child = (order_crossover(p1, p2, rng)
                     if rng.random() < cx_rate else p1.copy())
            if rng.random() < mut_rate:
                child = swap_mutation(child, rng)
            new_pop.append(child)
        pop = new_pop
        fits = [problem.fitness(p) for p in pop]
        best = max(fits)
        history.append(best)
        if verbose and (gen + 1) % 50 == 0:
            print(f"  gen {gen+1:4d}: best={best:.4f}")

    bi = int(np.argmax(fits))
    best_perm, best_fit = pop[bi], fits[bi]
    if polish:
        best_perm, best_fit = two_opt(problem, best_perm)
        if verbose:
            print(f"  2-opt polish: {fits[bi]:.4f} -> {best_fit:.4f}")
        history.append(best_fit)
    return {"best_perm": best_perm, "best_fitness": best_fit, "history": history}


if __name__ == "__main__":
    from problem import TTDPProblem
    from cbf import ContentBasedFilter

    cbf = ContentBasedFilter()
    ids, sat = cbf.candidates(2, "museum sejarah budaya", "menengah")
    prob = TTDPProblem(ids, n_days=2, start_day="Sabtu", satisfaction=sat)
    print(f"Kandidat: {prob.n} | GA pop={config.GA_POP_SIZE} gen={config.GA_N_GEN}")
    res = run_ga(prob, verbose=True)
    print(f"\nBest fitness: {res['best_fitness']:.4f}")
    print(f"Fitness gen-1 vs akhir: {res['history'][0]:.4f} -> {res['history'][-1]:.4f}")
    d = prob.decode(res["best_perm"])
    print(f"Terkunjungi {len(d['visited'])} venue | travel {d['travel_total']:.0f} mnt "
          f"| cross-zone {d['cross_zone']} | pelanggaran {d['violations']}")
    for di, day in enumerate(d["days"]):
        print(f"  Hari {di+1}:")
        for v in day:
            print(f"    {int(v['start'])//60:02d}:{int(v['start'])%60:02d} "
                  f"{v['name'][:45]}")

"""
ACO-SA Hybrid (Ant Colony Optimization + Simulated Annealing) untuk TTDP.

Port dari notebook ACO-SA rekan (representasi zona-toy 4-slot/hari) ke
representasi permutasi TTDPProblem — sama seperti gwo_ts.py:

  ACO (konstruksi rute — analog kerangka populasi GA/PSO):
    - Tiap semut membangun SATU PERMUTASI PENUH kandidat (bukan subset 4
      tempat seperti notebook, karena representasi TTDPProblem = permutasi
      utuh; seleksi subset terjadi otomatis di problem.decode() lewat
      time-budget). Konstruksi: mulai dari kandidat acak, tiap langkah pilih
      kandidat berikut via roulette-wheel berbobot
        (feromon^ALPHA) * (heuristik^BETA)
      heuristik = satisfaction(cand) / (travel_min(current, cand) + 1) —
      padanan langsung dari 'score / (travel_time+1)' notebook.
    - Feromon disimpan per pasangan INDEX kandidat (bukan venue_id — index
      stabil selama satu problem instance, lebih murah di-hash).

  SA (intensifikasi semut terbaik tiap iterasi — analog polish TS/2-opt):
    - Neighbor: swap 2 posisi ATAU insertion 1 elemen (padanan operasi
      SWAP/REPLACE notebook; REPLACE aslinya mengganti 1 slot dengan venue
      lain se-zona — di ruang permutasi utuh yang ekuivalen adalah
      memindah 1 elemen ke posisi lain = insertion).
    - Penerimaan Boltzmann: solusi lebih baik selalu diterima; lebih buruk
      diterima dengan probabilitas exp(delta/T). Suhu turun geometrik
      T *= COOLING_RATE tiap langkah, berhenti saat T <= T_MIN.

  Update feromon tiap iterasi: penguapan global (x (1-rho)), lalu deposit
  pada edge (perm[i], perm[i+1]) rute hasil SA sebanding max(0, fitness)/100
  (skala sama dengan notebook; fitness TTDPProblem sudah bernilai wajar
  karena satisfaction dinormalisasi 0-1, beda skala dari fitness zona-toy
  0-787 tapi bentuk update-nya identik).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config


def _sa_neighbor(perm, rng):
    """Neighbor SA: swap 2 posisi (50%) atau insertion 1 elemen (50%) —
    padanan operasi SWAP/REPLACE notebook di ruang permutasi utuh."""
    p = perm.copy()
    n = len(p)
    if rng.random() < 0.5:
        i, j = rng.choice(n, size=2, replace=False)
        p[i], p[j] = p[j], p[i]
    else:
        i, j = int(rng.integers(n)), int(rng.integers(n))
        val = p[i]
        p = np.delete(p, i)
        p = np.insert(p, j, val)
    return p


def simulated_annealing(problem, perm, rng,
                        t_init=config.SA_T_INIT, t_min=config.SA_T_MIN,
                        cooling=config.SA_COOLING_RATE):
    """Penyempurnaan SA satu rute (elite ant). Returns (perm, fitness)."""
    current, current_fit = perm.copy(), problem.fitness(perm)
    best, best_fit = current.copy(), current_fit
    t = t_init
    while t > t_min:
        cand = _sa_neighbor(current, rng)
        cand_fit = problem.fitness(cand)
        delta = cand_fit - current_fit
        if delta > 0:
            current, current_fit = cand, cand_fit
            if cand_fit > best_fit:
                best, best_fit = cand.copy(), cand_fit
        elif rng.random() < np.exp(np.clip(delta / t, -700, 0)):
            current, current_fit = cand, cand_fit
        t *= cooling
    return best, best_fit


def _construct_ant_route(problem, pheromone, rng, alpha, beta):
    """Satu semut membangun permutasi lengkap via roulette-wheel
    feromon x heuristik (satisfaction / travel_time)."""
    n = problem.n
    ids = problem.candidates
    start = int(rng.integers(n))
    route = [start]
    remaining = set(range(n)) - {start}

    while remaining:
        cur = route[-1]
        cands = list(remaining)
        weights = np.empty(len(cands))
        for k, c in enumerate(cands):
            tau = pheromone.get((cur, c), 1.0)
            sat = problem.satisfaction.get(ids[c], 0.0)
            travel = problem.travel_min(ids[cur], ids[c])
            eta = sat / (travel + 1.0)
            weights[k] = (tau ** alpha) * max(eta, 1e-9) ** beta
        total = weights.sum()
        probs = weights / total if total > 0 else np.full(len(cands), 1.0 / len(cands))
        nxt = cands[rng.choice(len(cands), p=probs)]
        route.append(nxt)
        remaining.discard(nxt)

    return np.array(route)


def run_aco_sa(problem, seed=config.RANDOM_SEED,
              n_ants=config.ACO_N_ANTS, n_iter=config.ACO_SA_N_ITER,
              alpha=config.ACO_ALPHA, beta=config.ACO_BETA,
              evaporation=config.ACO_EVAPORATION,
              verbose=False, polish=True):
    """Returns dict: best_perm, best_fitness, history (best fitness/iterasi).

    polish=True: solusi akhir dirapikan 2-opt (konsisten dgn GA/PSO/Hybrid)."""
    rng = np.random.default_rng(seed)
    pheromone = {}
    gbest, gbest_fit = None, float("-inf")
    history = []

    for it in range(n_iter):
        routes = [_construct_ant_route(problem, pheromone, rng, alpha, beta)
                 for _ in range(n_ants)]
        fits = [problem.fitness(r) for r in routes]

        best_ant = routes[int(np.argmax(fits))]
        refined, refined_fit = simulated_annealing(problem, best_ant, rng)

        if refined_fit > gbest_fit:
            gbest, gbest_fit = refined.copy(), refined_fit
        history.append(gbest_fit)

        # penguapan
        for k in pheromone:
            pheromone[k] *= (1.0 - evaporation)
        # deposit pada edge rute hasil SA
        deposit = max(0.0, refined_fit) / 100.0
        for i in range(len(refined) - 1):
            u, v = int(refined[i]), int(refined[i + 1])
            pheromone[(u, v)] = pheromone.get((u, v), 1.0) + deposit
            pheromone[(v, u)] = pheromone.get((v, u), 1.0) + deposit

        if verbose and (it + 1) % 20 == 0:
            print(f"  iter {it+1:4d}: gbest={gbest_fit:.4f}")

    if polish:
        from local_search import two_opt
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
    print(f"Kandidat: {prob.n} | ACO-SA ants={config.ACO_N_ANTS} "
          f"iter={config.ACO_SA_N_ITER}")
    res = run_aco_sa(prob, verbose=True)
    print(f"\nBest fitness: {res['best_fitness']:.4f}")
    print(f"gbest iter-1 vs akhir: {res['history'][0]:.4f} -> {res['history'][-1]:.4f}")
    d = prob.decode(res["best_perm"])
    print(f"Terkunjungi {len(d['visited'])} | travel {d['travel_total']:.0f} mnt "
          f"| cross-zone {d['cross_zone']} | pelanggaran {d['violations']}")

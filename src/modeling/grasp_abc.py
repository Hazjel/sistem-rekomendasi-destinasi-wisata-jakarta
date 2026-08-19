"""
GRASP-ABC Hybrid (Greedy Randomized Adaptive Search + Artificial Bee Colony)
untuk TTDP.

Port dari notebook GRASP-ABC rekan ke representasi permutasi TTDPProblem —
sama seperti gwo_ts.py:

  GRASP (konstruksi populasi awal — analog init_population GA/PSO/GWO-TS):
    - Bangun permutasi elemen demi elemen: tiap langkah, sampel
      GRASP_SAMPLE_SIZE kandidat tersisa (notebook menguji SEMUA kandidat
      tersisa se-zona — di sini disampel karena ruang kandidat penuh bisa
      sampai puluhan, beda dari subset 4-tempat notebook), hitung fitness
      proyeksi tiap kandidat (rute sejauh ini + kandidat), bentuk Restricted
      Candidate List (RCL) dari yang skornya >= max - alpha*(max-min), lalu
      pilih SATU acak dari RCL. alpha=0 -> greedy murni, alpha=1 -> random
      murni; GRASP_RCL_ALPHA di config mengontrol keseimbangannya.
    - Dipakai dua kali: (1) inisialisasi seluruh populasi bee, (2) scout
      phase — membangun ulang sumber makanan yang mandek.

  ABC (perbaikan populasi via 3 fase lebah — analog badan iterasi algoritma
  lain):
    - Employed bees: tiap sumber makanan dicoba 1 neighbor (mutate = pindah
      1 elemen ke posisi lain, padanan operasi 'replace' notebook di ruang
      permutasi utuh); simpan bila lebih baik, else tambah counter trial.
    - Onlooker bees: pilih sumber via roulette-wheel proporsional fitness
      (skor negatif -> probabilitas 0, dinormalisasi ulang), coba 1 neighbor.
    - Scout bees: sumber dgn trial > ABC_SCOUT_LIMIT dibuang, dibangun ulang
      via GRASP (bukan random murni — mempertahankan bias GRASP notebook).

  Polish 2-opt akhir ditambahkan (notebook aslinya tidak) — konsisten dgn
  prinsip di local_search.py: "diterapkan seragam ke ketiga [semua]
  algoritma demi fair comparison tetap terjaga".
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config


def _project_fitness(problem, partial_perm):
    """Fitness proyeksi rute parsial (padding sisa kandidat di posisi asal
    problem.candidates, di luar partial, agar tetap permutasi lengkap valid
    untuk problem.fitness — konsisten dgn cara notebook menilai rute
    parsialnya sendiri: makin bagus urutan sejauh ini, makin tinggi skor)."""
    n = problem.n
    used = set(int(x) for x in partial_perm)
    rest = [i for i in range(n) if i not in used]
    full = np.array(list(partial_perm) + rest)
    return problem.fitness(full)


def grasp_construct(problem, rng, alpha=config.GRASP_RCL_ALPHA,
                    sample_size=config.GRASP_SAMPLE_SIZE):
    """Bangun satu permutasi lengkap via Greedy Randomized Adaptive
    construction. Returns np.ndarray index kandidat."""
    n = problem.n
    route = []
    remaining = list(range(n))

    while remaining:
        pool = (list(rng.choice(remaining, size=min(sample_size, len(remaining)),
                                replace=False))
               if len(remaining) > sample_size else remaining)

        scores = [(_project_fitness(problem, route + [c]), c) for c in pool]
        max_fit = max(scores, key=lambda x: x[0])[0]
        min_fit = min(scores, key=lambda x: x[0])[0]
        threshold = max_fit - alpha * (max_fit - min_fit)
        rcl = [c for f, c in scores if f >= threshold] or pool

        chosen = int(rng.choice(rcl))
        route.append(chosen)
        remaining.remove(chosen)

    return np.array(route)


def _neighbor(perm, rng):
    """Insertion 1 elemen — padanan 'mutate' notebook (ganti 1 slot dengan
    venue lain) di ruang permutasi utuh."""
    p = perm.copy()
    n = len(p)
    i, j = int(rng.integers(n)), int(rng.integers(n))
    val = p[i]
    p = np.delete(p, i)
    p = np.insert(p, j, val)
    return p


def run_grasp_abc(problem, seed=config.RANDOM_SEED,
                  pop_size=config.GRASP_POP_SIZE, n_iter=config.GRASP_ABC_N_ITER,
                  alpha=config.GRASP_RCL_ALPHA, scout_limit=config.ABC_SCOUT_LIMIT,
                  verbose=False, polish=True):
    """Returns dict: best_perm, best_fitness, history (best fitness/iterasi)."""
    rng = np.random.default_rng(seed)

    sources = [grasp_construct(problem, rng, alpha) for _ in range(pop_size)]
    fits = [problem.fitness(s) for s in sources]
    trials = [0] * pop_size

    gi = int(np.argmax(fits))
    gbest, gbest_fit = sources[gi].copy(), fits[gi]
    history = []

    for it in range(n_iter):
        # A. employed bees
        for i in range(pop_size):
            nb = _neighbor(sources[i], rng)
            f = problem.fitness(nb)
            if f > fits[i]:
                sources[i], fits[i], trials[i] = nb, f, 0
            else:
                trials[i] += 1

        # B. onlooker bees (roulette-wheel proporsional fitness positif)
        shifted = np.array(fits) - min(min(fits), 0.0)   # geser agar >= 0
        total = shifted.sum()
        probs = (shifted / total if total > 0
                else np.full(pop_size, 1.0 / pop_size))
        for _ in range(pop_size):
            si = int(rng.choice(pop_size, p=probs))
            nb = _neighbor(sources[si], rng)
            f = problem.fitness(nb)
            if f > fits[si]:
                sources[si], fits[si], trials[si] = nb, f, 0
            else:
                trials[si] += 1

        # C. scout bees
        for i in range(pop_size):
            if trials[i] > scout_limit:
                sources[i] = grasp_construct(problem, rng, alpha)
                fits[i] = problem.fitness(sources[i])
                trials[i] = 0

        gi = int(np.argmax(fits))
        if fits[gi] > gbest_fit:
            gbest, gbest_fit = sources[gi].copy(), fits[gi]
        history.append(gbest_fit)

        if verbose and (it + 1) % 10 == 0:
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
    print(f"Kandidat: {prob.n} | GRASP-ABC pop={config.GRASP_POP_SIZE} "
          f"iter={config.GRASP_ABC_N_ITER}")
    res = run_grasp_abc(prob, verbose=True)
    print(f"\nBest fitness: {res['best_fitness']:.4f}")
    print(f"gbest iter-1 vs akhir: {res['history'][0]:.4f} -> {res['history'][-1]:.4f}")
    d = prob.decode(res["best_perm"])
    print(f"Terkunjungi {len(d['visited'])} | travel {d['travel_total']:.0f} mnt "
          f"| cross-zone {d['cross_zone']} | pelanggaran {d['violations']}")

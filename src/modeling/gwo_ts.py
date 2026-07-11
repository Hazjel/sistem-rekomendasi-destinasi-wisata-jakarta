"""
GWO-TS Hybrid (Grey Wolf Optimizer + Tabu Search) untuk TTDP.

Port dari notebook GWO-TS ke representasi permutasi TTDPProblem (sama seperti
GA/PSO/Hybrid — index kandidat, decode time-budget di problem.py). Struktur
algoritma dipertahankan persis dari notebook; hanya operator yang disesuaikan
dari formulasi zona-toy ke permutasi:

  GWO (pencarian global — analog kerangka PSO di hybrid lama):
    - 3 leader: alpha/beta/delta = tiga wolf terbaik.
    - a = 2 - it*(2/n_iter). A = 2*a*r - a.
    - |A|<1  -> eksploitasi: tarik wolf ke delta (prob rendah), beta, lalu
      alpha (prob tertinggi) via swap-sequence. Tarikan progresif = makin
      dekat leader terbaik makin kuat.
    - |A|>=1 -> eksplorasi: swap-mutation acak 2x.
    Di notebook ada operator 'replace' (ganti venue dari zona sama) karena
    individu = subset 4 venue. Di TTDPProblem himpunan kandidat TETAP, cuma
    urutan yang dioptimasi -> swap-sequence murni (tanpa replace), eksplorasi
    pakai swap-mutation. Ekuivalen fungsional dengan peran 'replace' di sana.

  TS (intensifikasi lokal — mengambil peran 2-opt polish algoritma lain):
    - Tiap iterasi GWO, alpha di-refine: bangkitkan TS_MAX_NEIGHBORS neighbor
      (swap 2 posisi ATAU insertion 1 elemen), pilih terbaik yang non-tabu
      (aspiration: move tabu tetap diterima bila > best lokal).
    - tabu-list FIFO menyimpan tuple permutasi yang baru diterima, panjang
      TS_TENURE.
    - Polish akhir: beberapa pass TS dengan neighborhood diperbesar.

Wolf indeks 0 dijaga elit (tidak digerakkan), selalu diisi alpha hasil TS —
menjamin fitness alpha monoton tak turun antar iterasi.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

from ga import swap_mutation
from pso import swap_sequence


def _apply_swaps_prob(perm, swaps, prob, rng):
    """Terapkan tiap swap (i, j) dengan probabilitas `prob` (semantik apply_swaps
    notebook — beda dari pso.apply_swaps yang menerapkan semua swap)."""
    p = perm.copy()
    for i, j in swaps:
        if rng.random() < prob:
            p[i], p[j] = p[j], p[i]
    return p


def tabu_search_refine(problem, perm, tabu_list, rng,
                       tenure=config.TS_TENURE,
                       max_neighbors=config.TS_MAX_NEIGHBORS):
    """Satu langkah Tabu Search di sekitar `perm`. Returns (perm, fitness).

    Neighborhood permutasi: swap 2 posisi atau insertion (cabut 1 elemen,
    sisipkan di posisi lain — analog operator 'replace' notebook di ruang
    permutasi). Tabu pada tuple permutasi utuh, aspiration bila lebih baik
    dari best lokal.
    """
    best = perm.copy()
    best_fit = problem.fitness(best)
    n = len(best)
    if n < 2:
        return best, best_fit

    cand_best, cand_fit = None, float("-inf")
    for _ in range(max_neighbors):
        nb = best.copy()
        if rng.random() < 0.5:
            i, j = rng.choice(n, size=2, replace=False)
            nb[i], nb[j] = nb[j], nb[i]
        else:
            i, j = int(rng.integers(n)), int(rng.integers(n))
            val = nb[i]
            nb = np.delete(nb, i)
            nb = np.insert(nb, j, val)
        key = tuple(int(x) for x in nb)
        fit = problem.fitness(nb)
        # non-tabu, atau tabu tapi lolos aspiration (> best lokal)
        if key not in tabu_list or fit > best_fit:
            if fit > cand_fit:
                cand_best, cand_fit = nb, fit

    if cand_best is not None and cand_fit > best_fit:
        tabu_list.append(tuple(int(x) for x in cand_best))
        if len(tabu_list) > tenure:
            tabu_list.pop(0)
        return cand_best, cand_fit
    return best, best_fit


def run_gwo_ts(problem, seed=config.RANDOM_SEED,
               n_wolves=config.GWO_N_WOLVES, n_iter=config.GWO_N_ITER,
               p_delta=config.GWO_PULL_DELTA, p_beta=config.GWO_PULL_BETA,
               p_alpha=config.GWO_PULL_ALPHA,
               tenure=config.TS_TENURE, max_neighbors=config.TS_MAX_NEIGHBORS,
               polish=True, polish_passes=config.TS_POLISH_PASSES,
               verbose=False):
    """Returns dict: best_perm, best_fitness, history (best fitness/iterasi).

    polish=True: intensifikasi TS akhir (neighborhood diperbesar) — peran
    setara 2-opt polish di GA/PSO/Hybrid, tapi tetap murni GWO-TS.
    """
    rng = np.random.default_rng(seed)
    wolves = problem.init_population(n_wolves, rng)
    fits = [problem.fitness(w) for w in wolves]

    order = np.argsort(fits)[::-1]
    alpha, alpha_fit = wolves[order[0]].copy(), fits[order[0]]
    beta = wolves[order[1]].copy()
    delta = wolves[order[2]].copy()

    tabu_list, history = [], []

    for it in range(n_iter):
        a = 2.0 - it * (2.0 / n_iter)

        # wolf 0 = elit, dilewati (diisi alpha hasil TS di akhir iterasi)
        for i in range(1, n_wolves):
            A = 2 * a * rng.random() - a
            w = wolves[i].copy()
            if abs(A) < 1.0:
                # eksploitasi: tarik progresif ke delta -> beta -> alpha
                w = _apply_swaps_prob(w, swap_sequence(w, delta), p_delta, rng)
                w = _apply_swaps_prob(w, swap_sequence(w, beta), p_beta, rng)
                w = _apply_swaps_prob(w, swap_sequence(w, alpha), p_alpha, rng)
            else:
                # eksplorasi: dua swap-mutation acak (analog mutate 2x notebook)
                w = swap_mutation(w, rng)
                w = swap_mutation(w, rng)
            wolves[i] = w

        fits = [problem.fitness(w) for w in wolves]
        order = np.argsort(fits)[::-1]
        if fits[order[0]] > alpha_fit:
            alpha, alpha_fit = wolves[order[0]].copy(), fits[order[0]]
        beta = wolves[order[1]].copy()
        delta = wolves[order[2]].copy()

        # intensifikasi TS pada alpha; tulis balik ke elit wolf 0 bila membaik
        ref, ref_fit = tabu_search_refine(problem, alpha, tabu_list, rng,
                                          tenure, max_neighbors)
        if ref_fit > alpha_fit:
            alpha, alpha_fit = ref.copy(), ref_fit
            wolves[0] = alpha.copy()

        history.append(alpha_fit)
        if verbose and (it + 1) % 20 == 0:
            print(f"  iter {it+1:4d}: alpha={alpha_fit:.4f}")

    if polish:
        pre = alpha_fit
        for _ in range(polish_passes):
            ref, ref_fit = tabu_search_refine(problem, alpha, tabu_list, rng,
                                              tenure, max_neighbors * 4)
            if ref_fit > alpha_fit:
                alpha, alpha_fit = ref.copy(), ref_fit
        if verbose:
            print(f"  TS polish: {pre:.4f} -> {alpha_fit:.4f}")
        history.append(alpha_fit)

    return {"best_perm": alpha, "best_fitness": alpha_fit, "history": history}


if __name__ == "__main__":
    from problem import TTDPProblem
    from cbf import ContentBasedFilter

    cbf = ContentBasedFilter()
    ids, sat = cbf.candidates(2, "museum sejarah budaya", "menengah")
    prob = TTDPProblem(ids, n_days=2, start_day="Sabtu", satisfaction=sat)
    print(f"Kandidat: {prob.n} | GWO-TS wolves={config.GWO_N_WOLVES} "
          f"iter={config.GWO_N_ITER} tenure={config.TS_TENURE}")
    res = run_gwo_ts(prob, verbose=True)
    print(f"\nBest fitness: {res['best_fitness']:.4f}")
    print(f"alpha iter-1 vs akhir: {res['history'][0]:.4f} -> {res['history'][-1]:.4f}")
    d = prob.decode(res["best_perm"])
    print(f"Terkunjungi {len(d['visited'])} | travel {d['travel_total']:.0f} mnt "
          f"| cross-zone {d['cross_zone']} | pelanggaran {d['violations']}")

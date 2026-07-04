"""
Local search 2-opt untuk polish solusi akhir GA/PSO/Hybrid.

Metaheuristik populasi bagus untuk eksplorasi global tapi lemah merapikan
urutan LOKAL (mis. pola bolak-balik: TMII -> venue jauh -> balik TMII).
2-opt menambal ini: coba semua pembalikan segmen perm[i..j]; terima kalau
fitness naik (first-improvement), ulang sampai satu pass penuh tanpa
perbaikan atau max_pass tercapai.

Diterapkan seragam ke ketiga algoritma (fair comparison tetap terjaga) —
pola memetic/hybrid metaheuristic yang standar di literatur TTDP/TSP.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config  # noqa: F401  (konsisten dgn modul lain; tak ada param 2-opt khusus)


def two_opt(problem, perm, max_pass=5):
    """Perbaiki permutasi via 2-opt (segment reversal), maximize fitness.

    Returns (perm_terbaik, fitness_terbaik). Monoton naik — hasil tidak
    pernah lebih buruk dari input.
    """
    best = perm.copy()
    best_fit = problem.fitness(best)
    n = len(best)
    for _ in range(max_pass):
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = best.copy()
                cand[i:j + 1] = cand[i:j + 1][::-1]
                f = problem.fitness(cand)
                if f > best_fit:
                    best, best_fit = cand, f
                    improved = True
        if not improved:
            break
    return best, best_fit

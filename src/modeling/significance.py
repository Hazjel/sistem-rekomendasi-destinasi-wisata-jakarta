"""
Uji signifikansi statistik & statistik deskriptif untuk perbandingan optimizer.

Menjawab dua permintaan reviewer paper:
  #3 Uji signifikansi — beda rata-rata antar algoritma bisa saja kebetulan
     (variansi antar-run besar). Dipakai uji NON-PARAMETRIK standar untuk
     perbandingan metaheuristik:
       - Friedman (omnibus): apakah ADA beda di antara semua algoritma?
       - Wilcoxon signed-rank (posthoc): pasangan MANA yang berbeda,
         dengan koreksi Bonferroni untuk multiple comparison.
     Non-parametrik dipilih karena fitness tak berdistribusi normal; uji
     berpasangan valid karena seed identik antar algoritma (lihat di bawah).
  #5 USS mean +- std per algoritma — sebelumnya hanya mean yang dilaporkan.

Blok berpasangan = (scenario, run). `experiment.py` memakai
seed = RANDOM_SEED + run, jadi run ke-i memakai seed yang SAMA untuk semua
algoritma -> instance masalah identik -> pasangan sah untuk uji berpasangan.

Modul sengaja dipisah dari notebook & generik terhadap sumber CSV: argumen
`--results-csv` memungkinkan analisis yang sama dijalankan pada hasil
eksperimen lain (mis. himpunan algoritma yang lebih lengkap), asalkan CSV
punya kolom: scenario, algorithm, run, + metrik yang diuji.

Jalankan:
    python src/modeling/significance.py
    python src/modeling/significance.py --results-csv path/lain.csv
"""
import argparse
import os
import sys
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config

ALPHA = 0.05
DEFAULT_METRICS = ["fitness", "uss", "runtime_sec"]
# Arah "lebih baik": runtime makin kecil makin baik, sisanya makin besar.
LOWER_IS_BETTER = {"runtime_sec", "travel_min", "violations"}
METRIC_LABEL = {"fitness": "Fitness", "uss": "USS (User Satisfaction Score)",
                "runtime_sec": "Runtime (s)"}


def _pivot(df, metric, algos):
    """Matriks berpasangan: baris = (scenario, run), kolom = algoritma."""
    piv = df.pivot_table(index=["scenario", "run"], columns="algorithm",
                         values=metric)
    missing = [a for a in algos if a not in piv.columns]
    if missing:
        raise ValueError(f"algoritma tak ada di CSV: {missing}")
    return piv[algos].dropna()


def run_tests(df, metric, algos, alpha=ALPHA):
    """Friedman omnibus + Wilcoxon posthoc (Bonferroni) untuk satu metrik.

    Returns dict: n_blocks, chi2, p, significant, ranks (Series, 1=terbaik),
    posthoc (DataFrame; kosong bila omnibus tak signifikan), per_scenario (list).
    """
    piv = _pivot(df, metric, algos)
    lower_better = metric in LOWER_IS_BETTER
    chi2, p = friedmanchisquare(*[piv[a] for a in algos])

    # rank 1 = terbaik; untuk metrik "makin kecil makin baik" urutan dibalik
    ranks = piv.rank(axis=1, ascending=lower_better).mean().sort_values()

    per_scenario = []
    for sc in df["scenario"].unique():
        sub = _pivot(df[df.scenario == sc].assign(scenario=sc), metric, algos)
        if len(sub) < 3:                      # Friedman butuh >=3 blok
            continue
        c2, pv = friedmanchisquare(*[sub[a] for a in algos])
        best = sub.rank(axis=1, ascending=lower_better).mean().idxmin()
        per_scenario.append({"scenario": sc, "chi2": round(c2, 3),
                             "p_value": pv, "significant": pv < alpha,
                             "rank1": best})

    posthoc = pd.DataFrame()
    if p < alpha:
        pairs = list(combinations(algos, 2))
        alpha_corr = alpha / len(pairs)       # koreksi Bonferroni
        rows = []
        for a, b in pairs:
            try:
                _, pw = wilcoxon(piv[a], piv[b])
            except ValueError:                # semua selisih nol -> identik
                pw = 1.0
            if lower_better:
                better = a if piv[a].mean() < piv[b].mean() else b
            else:
                better = a if piv[a].mean() > piv[b].mean() else b
            rows.append({"metric": metric, "pair": f"{a} vs {b}",
                         "p_value": pw, "alpha_bonferroni": alpha_corr,
                         "significant": pw < alpha_corr, "better": better})
        posthoc = pd.DataFrame(rows)

    return {"metric": metric, "n_blocks": len(piv), "chi2": chi2, "p": p,
            "significant": p < alpha, "ranks": ranks, "posthoc": posthoc,
            "per_scenario": per_scenario, "lower_is_better": lower_better}


def descriptive(df, metric, algos):
    """Statistik deskriptif metrik: agregat & per skenario (jawaban #5)."""
    agg = (df.groupby("algorithm")[metric]
             .agg(["mean", "std", "min", "max"]).reindex(algos).round(4))
    per_sc = (df.groupby(["scenario", "algorithm"])[metric]
                .agg(["mean", "std"]).round(4))
    return agg, per_sc


# --------------------------------------------------------------------------
# Ekspor LaTeX (booktabs) — siap tempel ke naskah
# --------------------------------------------------------------------------
def _esc(s):
    return str(s).replace("_", r"\_").replace("&", r"\&")


def to_latex_descriptive(agg, metric, label=None, caption=None):
    lab = label or METRIC_LABEL.get(metric, metric)
    best = agg["mean"].idxmin() if metric in LOWER_IS_BETTER else agg["mean"].idxmax()
    lines = [
        r"\begin{table}[t]", r"  \centering",
        f"  \\caption{{{caption or f'{lab} per optimizer (mean $\\pm$ std over all runs).'}}}",
        f"  \\label{{tab:{metric}_desc}}",
        r"  \begin{tabular}{@{}l c c c@{}}", r"    \toprule",
        f"    \\textbf{{Optimizer}} & \\textbf{{Mean $\\pm$ Std}} & "
        r"\textbf{Min} & \textbf{Max} \\", r"    \midrule",
    ]
    for algo, r in agg.iterrows():
        name = _esc(algo).replace("GWO-TS", "GWO--TS")
        cell = f"{r['mean']:.4f} $\\pm$ {r['std']:.4f}"
        if algo == best:
            cell = r"\textbf{" + cell + "}"
        lines.append(f"    {name} & {cell} & {r['min']:.4f} & {r['max']:.4f} \\\\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def to_latex_tests(results, alpha=ALPHA):
    """Tabel ringkas Friedman semua metrik."""
    lines = [
        r"\begin{table}[t]", r"  \centering",
        r"  \caption{Friedman test across optimizers (blocks = scenario "
        r"$\times$ run, identical seeds). $\alpha = " + f"{alpha}$.}}",
        r"  \label{tab:friedman}",
        r"  \begin{tabular}{@{}l c c c l@{}}", r"    \toprule",
        r"    \textbf{Metric} & $\chi^2$ & \textbf{$p$-value} & "
        r"\textbf{Significant} & \textbf{Best rank} \\", r"    \midrule",
    ]
    for r in results:
        lab = METRIC_LABEL.get(r["metric"], r["metric"]).split(" (")[0]
        p = r["p"]
        pstr = f"$<10^{{{int(np.floor(np.log10(p)))}}}$" if p < 1e-4 else f"{p:.4f}"
        sig = r"\textbf{yes}" if r["significant"] else "no"
        top = _esc(r["ranks"].index[0]).replace("GWO-TS", "GWO--TS")
        lines.append(f"    {lab} & {r['chi2']:.2f} & {pstr} & {sig} & "
                     f"{top} ({r['ranks'].iloc[0]:.2f}) \\\\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def to_latex_posthoc(posthoc, metric):
    if posthoc.empty:
        return ""
    lab = METRIC_LABEL.get(metric, metric).split(" (")[0]
    a_corr = posthoc["alpha_bonferroni"].iloc[0]
    lines = [
        r"\begin{table}[t]", r"  \centering",
        f"  \\caption{{Wilcoxon signed-rank post-hoc on {lab} "
        f"(Bonferroni-corrected $\\alpha = {a_corr:.4f}$).}}",
        f"  \\label{{tab:posthoc_{metric}}}",
        r"  \begin{tabular}{@{}l c c l@{}}", r"    \toprule",
        r"    \textbf{Pair} & \textbf{$p$-value} & \textbf{Significant} & "
        r"\textbf{Better} \\", r"    \midrule",
    ]
    for _, r in posthoc.iterrows():
        pair = _esc(r["pair"]).replace("GWO-TS", "GWO--TS")
        p = r["p_value"]
        pstr = f"$<10^{{{int(np.floor(np.log10(p)))}}}$" if p < 1e-4 else f"{p:.4f}"
        sig = r"\textbf{yes}" if r["significant"] else "no"
        better = _esc(r["better"]).replace("GWO-TS", "GWO--TS")
        lines.append(f"    {pair} & {pstr} & {sig} & {better} \\\\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def print_report(r):
    """Cetak hasil satu metrik ke stdout."""
    lab = METRIC_LABEL.get(r["metric"], r["metric"])
    arrow = "kecil = baik" if r["lower_is_better"] else "besar = baik"
    print(f"\n{'=' * 68}\n{lab}  ({arrow})\n{'=' * 68}")
    print(f"Friedman: chi2 = {r['chi2']:.3f}, p = {r['p']:.4g}  "
          f"-> {'SIGNIFIKAN' if r['significant'] else 'tidak signifikan'} "
          f"(n = {r['n_blocks']} blok)")
    print("Mean rank (1 = terbaik):")
    for a, v in r["ranks"].items():
        print(f"  {a:8s}: {v:.2f}")
    if r["per_scenario"]:
        print("Per skenario:")
        for s in r["per_scenario"]:
            print(f"  {s['scenario']:16s} chi2={s['chi2']:6.2f} "
                  f"p={s['p_value']:.4g} "
                  f"({'signifikan' if s['significant'] else 'tidak'}) "
                  f"| rank-1: {s['rank1']}")
    if not r["posthoc"].empty:
        print("Wilcoxon posthoc (Bonferroni):")
        for _, x in r["posthoc"].iterrows():
            mark = "SIG" if x["significant"] else " - "
            print(f"  {x['pair']:22s} p={x['p_value']:.5f} {mark} "
                  f"(lebih baik: {x['better']})")
    else:
        print("Posthoc tak dijalankan (omnibus tak signifikan) -> algoritma "
              "setara pada metrik ini.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--results-csv", default=config.EXPERIMENT_RESULTS_CSV,
                    help="CSV hasil eksperimen (default: config)")
    ap.add_argument("--metrics", default=",".join(DEFAULT_METRICS),
                    help="metrik dipisah koma")
    ap.add_argument("--algos", default=None,
                    help="urutan algoritma dipisah koma (default: dari CSV)")
    ap.add_argument("--out-dir", default="data/processed")
    ap.add_argument("--alpha", type=float, default=ALPHA)
    args = ap.parse_args()

    df = pd.read_csv(args.results_csv)
    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]
    if args.algos:
        algos = [a.strip() for a in args.algos.split(",")]
    else:
        preferred = ["GA", "PSO", "Hybrid", "GWO-TS"]
        found = list(df["algorithm"].unique())
        algos = [a for a in preferred if a in found] + \
                [a for a in found if a not in preferred]

    n_per = df.groupby(["scenario", "algorithm"]).size()
    print(f"Sumber   : {args.results_csv}")
    print(f"Algoritma: {algos}")
    print(f"Skenario : {list(df['scenario'].unique())}")
    print(f"Run per (skenario, algoritma): {sorted(n_per.unique())}")

    results, all_posthoc, latex = [], [], []
    for m in metrics:
        if m not in df.columns:
            print(f"[skip] kolom '{m}' tak ada di CSV")
            continue
        r = run_tests(df, m, algos, args.alpha)
        print_report(r)
        results.append(r)
        if not r["posthoc"].empty:
            all_posthoc.append(r["posthoc"])
            latex.append(to_latex_posthoc(r["posthoc"], m))

    os.makedirs(args.out_dir, exist_ok=True)

    # Friedman semua metrik
    tests_csv = os.path.join(args.out_dir, "significance_tests.csv")
    pd.DataFrame([{"metric": r["metric"], "n_blocks": r["n_blocks"],
                   "chi2": round(r["chi2"], 4), "p_value": r["p"],
                   "significant": r["significant"],
                   "best_rank_algo": r["ranks"].index[0],
                   "best_rank_value": round(r["ranks"].iloc[0], 3)}
                  for r in results]).to_csv(tests_csv, index=False)
    print(f"\nTersimpan -> {tests_csv}")

    if all_posthoc:
        ph = os.path.join(args.out_dir, "significance_posthoc.csv")
        pd.concat(all_posthoc, ignore_index=True).to_csv(ph, index=False)
        print(f"Tersimpan -> {ph}")

    # Deskriptif USS (#5) — dan metrik lain bila diminta
    for m in metrics:
        if m not in df.columns:
            continue
        agg, per_sc = descriptive(df, m, algos)
        if m == "uss":
            print(f"\n{'=' * 68}\nUSS mean +- std (jawaban reviewer #5)\n{'=' * 68}")
            print(agg.to_string())
            print("\nPer skenario:")
            print(per_sc.to_string())
            out = os.path.join(args.out_dir, "uss_descriptive.csv")
            agg.to_csv(out)
            per_sc.to_csv(os.path.join(args.out_dir, "uss_descriptive_by_scenario.csv"))
            print(f"\nTersimpan -> {out}")
        latex.append(to_latex_descriptive(agg, m))

    latex.insert(0, to_latex_tests(results, args.alpha))
    tex = os.path.join(args.out_dir, "paper_tables.tex")
    with open(tex, "w", encoding="utf-8") as f:
        f.write("% Tabel hasil uji signifikansi & deskriptif — siap tempel.\n"
                "% Dihasilkan src/modeling/significance.py\n"
                f"% Sumber data: {args.results_csv}\n\n")
        f.write("\n\n".join(t for t in latex if t))
    print(f"Tersimpan -> {tex}")


if __name__ == "__main__":
    main()

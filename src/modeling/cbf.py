"""
Content-Based Filtering (FASE 1) — TF-IDF + cosine similarity + filter budget.

Reuse pendekatan src/api/recommend.py (TF-IDF venue_category + description),
ditambah:
  - filter budget via proxy kategori (config.CATEGORY_PRICE_LEVEL — price_level
    Google kosong utk hampir semua venue, dideklarasikan sbg estimasi di laporan)
  - output: kandidat top-N + skor satisfaction utk fitness GA/PSO
    satisfaction = W_SIM * skor_CBF + W_POP * rating_norm   (config)
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import minmax_scale

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config


class ContentBasedFilter:
    def __init__(self, csv_path=None):
        if csv_path is None:
            csv_path = config.CLUSTERED_VENUES_CSV
        self.df = pd.read_csv(csv_path)
        texts = (self.df["venue_category"].fillna("") + " " +
                 self.df["description"].fillna(""))
        self._tfidf = TfidfVectorizer(token_pattern=r"[^:\s]+")
        self._mat = self._tfidf.fit_transform(texts)
        # Popularitas: Bayesian weighted rating (formula IMDB) — rating mentah
        # bias ke venue sepi (5.0 dari 4 review > Monas 4.6 dari 122rb review).
        # WR = (v/(v+m))*R + (m/(v+m))*C ; m = median jumlah review, C = mean rating.
        rating = pd.to_numeric(self.df["google_rating"], errors="coerce").fillna(0)
        count = pd.to_numeric(self.df["google_rating_count"], errors="coerce").fillna(0)
        m = count.median()
        c_mean = rating[rating > 0].mean()
        weighted = (count / (count + m)) * rating + (m / (count + m)) * c_mean
        self.df["_pop"] = minmax_scale(weighted)
        self.df["_price"] = self.df["venue_category"].map(
            lambda c: config.CATEGORY_PRICE_LEVEL.get(
                c, config.CATEGORY_PRICE_LEVEL["DEFAULT"]))

    def score(self, preference_text=None, budget=None):
        """Skor CBF + satisfaction utk semua venue.

        preference_text : teks preferensi turis, mis. "museum sejarah budaya"
                          (None -> similarity 0, satisfaction = popularitas saja)
        budget          : 'hemat' / 'menengah' / 'bebas' / None (tanpa filter)

        Returns DataFrame (venue_id, name, venue_category, cbf_score,
        satisfaction) terurut satisfaction desc — venue di atas budget
        di-exclude (filter keras).
        """
        df = self.df
        if preference_text:
            q = self._tfidf.transform([preference_text])
            sim = cosine_similarity(q, self._mat).ravel()
        else:
            sim = np.zeros(len(df))

        satisfaction = (config.FITNESS_W_SIM * sim
                        + config.FITNESS_W_POP * df["_pop"].values)

        out = df.assign(cbf_score=sim.round(4),
                        satisfaction=satisfaction.round(4))
        if budget is not None:
            max_lv = config.BUDGET_LEVELS[budget]
            out = out[out["_price"] <= max_lv]
        cols = ["venue_id", "name", "venue_category", "zone_id",
                "cbf_score", "satisfaction"]
        return out.sort_values("satisfaction", ascending=False)[cols]

    def candidates(self, n_days, preference_text=None, budget=None,
                   per_day=config.CANDIDATES_PER_DAY,
                   mmr_lambda=config.CBF_MMR_LAMBDA):
        """Top-N kandidat utk optimizer (N = per_day x n_days), seleksi MMR.

        MMR (Maximal Marginal Relevance): kandidat dipilih iteratif —
        skor = lambda*satisfaction - (1-lambda)*max_cosine_sim ke kandidat
        yang sudah terpilih. Mencegah kandidat didominasi venue kembar
        (mis. 21 Anjungan TMII yang deskripsinya hampir identik).
        mmr_lambda=1.0 -> murni relevansi (tanpa diversity).

        Returns (list venue_id, dict venue_id -> satisfaction).
        """
        n = per_day * n_days
        scored = self.score(preference_text, budget)
        if mmr_lambda >= 1.0 or len(scored) <= n:
            scored = scored.head(n)
            ids = scored["venue_id"].tolist()
            sat = dict(zip(scored["venue_id"], scored["satisfaction"]))
            return ids, sat

        # pool = 3N teratas (MMR di seluruh dataset mahal & tak perlu)
        pool = scored.head(3 * n)
        pos = {vid: i for i, vid in enumerate(self.df["venue_id"])}
        rows = [pos[v] for v in pool["venue_id"]]
        sim_mat = cosine_similarity(self._mat[rows])       # antar kandidat pool
        rel = pool["satisfaction"].to_numpy()

        selected = [0]                                     # mulai dari top-1
        remaining = list(range(1, len(pool)))
        while len(selected) < n and remaining:
            max_sim = sim_mat[np.ix_(remaining, selected)].max(axis=1)
            mmr = mmr_lambda * rel[remaining] - (1 - mmr_lambda) * max_sim
            selected.append(remaining.pop(int(np.argmax(mmr))))

        chosen = pool.iloc[selected]
        ids = chosen["venue_id"].tolist()
        sat = dict(zip(chosen["venue_id"], chosen["satisfaction"]))
        return ids, sat


if __name__ == "__main__":
    cbf = ContentBasedFilter()
    print("=== Preferensi: 'museum sejarah budaya' | budget hemat | 2 hari ===")
    ids, sat = cbf.candidates(2, "museum sejarah budaya", "hemat")
    top = cbf.score("museum sejarah budaya", "hemat").head(10)
    print(top.to_string(index=False))
    print(f"\nKandidat: {len(ids)} venue")

    print("\n=== Tanpa preferensi | budget bebas ===")
    top2 = cbf.score(None, "bebas").head(5)
    print(top2.to_string(index=False))

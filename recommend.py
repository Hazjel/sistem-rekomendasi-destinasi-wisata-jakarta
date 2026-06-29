"""
Engine rekomendasi HYBRID = content-based + geo + popularity + time-of-week.

Skor akhir per kandidat venue:
    score = w_sim * similarity_konten
          + w_geo * kedekatan_jarak
          + w_pop * popularitas (visitor ternormalisasi)
          + w_day * keramaian_hari_terpilih

Tanpa riwayat user (cold-start friendly). Turis kasih: lokasi (lat/lon),
opsional kategori favorit & hari kunjungan -> dapat top-N destinasi.
"""
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import minmax_scale

import config

DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

WEIGHTS = {"sim": 0.30, "geo": 0.35, "pop": 0.20, "day": 0.15}


def haversine(lat1, lon1, lat2, lon2):
    """Jarak km antar koordinat (vectorized)."""
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


class Recommender:
    def __init__(self, csv_path=config.ENRICHED_CSV):
        self.df = pd.read_csv(csv_path)
        # vektor konten dari kategori (bisa ditambah nama/tag bila ada).
        self._tfidf = TfidfVectorizer(token_pattern=r"[^:]+")
        self._mat = self._tfidf.fit_transform(self.df["venue_category"])
        # popularitas ternormalisasi 0..1.
        self.df["_pop"] = minmax_scale(self.df["unique_visitors"])

    def recommend(self, lat, lon, category=None, day=None,
                  max_km=25.0, top_n=10, only_open=False):
        df = self.df
        # 1) similarity konten terhadap kategori minat (default: netral).
        if category:
            q = self._tfidf.transform([category])
            sim = cosine_similarity(q, self._mat).ravel()
        else:
            sim = np.zeros(len(df))

        # 2) geo: jarak -> kedekatan (closer = higher).
        dist = haversine(lat, lon, df["latitude"].values, df["longitude"].values)
        geo = np.clip(1 - dist / max_km, 0, 1)

        # 3) popularitas.
        pop = df["_pop"].values

        # 4) buka di hari terpilih: skor 1 kalau buka, 0 kalau tutup.
        if day in DAYS:
            open_col = df[f"{day}_buka"].astype(str)
            is_open = (open_col != "Tutup").astype(float).values
            jam = open_col + " - " + df[f"{day}_tutup"].astype(str)
        else:
            is_open = np.ones(len(df))
            jam = ""

        score = (WEIGHTS["sim"] * sim + WEIGHTS["geo"] * geo
                 + WEIGHTS["pop"] * pop + WEIGHTS["day"] * is_open)

        out = df.assign(distance_km=dist.round(2), score=score.round(4),
                        jam_buka=jam)
        out = out[out["distance_km"] <= max_km]
        # opsi: hanya tampilkan yang buka di hari terpilih.
        if only_open and day in DAYS:
            out = out[out["jam_buka"].str.split(" - ").str[0] != "Tutup"]
        cols = ["venue_id", "name", "venue_category", "distance_km",
                "jam_buka", "unique_visitors", "time_spent", "References", "score"]
        return out.sort_values("score", ascending=False).head(top_n)[cols]


if __name__ == "__main__":
    rec = Recommender()
    # contoh: turis di Monas, suka museum, kunjungan Sabtu.
    res = rec.recommend(lat=-6.1754, lon=106.8272,
                        category="tourism:museum", day="Sabtu", top_n=10)
    print(res.to_string(index=False))

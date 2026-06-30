"""
Cluster venue per zona geografis (K-Means by lat/lon) -> kolom zone_id.

Fase 1 riset (pptx): "Mengelompokkan POI berdasarkan lokasi geografis ...
untuk memudahkan penjadwalan per hari (cluster per zona wilayah Jakarta)".
Hasil zone_id jadi basis scope time_matrix (04_time_matrix/) -- matrix
dihitung hanya antar-venue dalam zone_id sama, bukan all-pairs se-Jakarta.

Output: data/processed/clustered_venues.csv
"""
import os
import sys

import pandas as pd
from sklearn.cluster import KMeans

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def main():
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    print(f"Venue input (merged): {len(df)}")

    coords = df[["latitude", "longitude"]].to_numpy()
    km = KMeans(n_clusters=config.CLUSTER_K, random_state=config.RANDOM_SEED, n_init=10)
    df["zone_id"] = km.fit_predict(coords)

    print(f"\nDistribusi venue per zone (k={config.CLUSTER_K}):")
    print(df["zone_id"].value_counts().sort_index().to_string())

    print("\nTop kategori per zone:")
    for zone in sorted(df["zone_id"].unique()):
        top_cat = df[df["zone_id"] == zone]["venue_category"].value_counts().head(3)
        print(f"  zone {zone}: {dict(top_cat)}")

    os.makedirs(os.path.dirname(config.CLUSTERED_VENUES_CSV), exist_ok=True)
    df.to_csv(config.CLUSTERED_VENUES_CSV, index=False)
    print(f"\nTersimpan -> {config.CLUSTERED_VENUES_CSV}")


if __name__ == "__main__":
    main()

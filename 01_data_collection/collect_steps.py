"""
Unduh dataset Massive-STEPS-Jakarta (HuggingFace) -- check-in nyata (GPS +
user behavior), pelengkap OSM yang tidak punya data trajectory/popularitas asli.

Level data: per check-in (412.100 row) -> diagregasi jadi per venue (1 row/venue,
checkin_count = proxy popularitas nyata, pengganti unique_visitors sintetis OSM).

Output:
    data/raw/steps_checkins_raw.csv  (level check-in, utk fase trail/sequence nanti)
    data/raw/steps_venues_raw.csv    (level venue, 1 row/venue, dipakai filter_tourism.py)
"""
import os
import sys

import pandas as pd
from huggingface_hub import hf_hub_download

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def main():
    os.makedirs(os.path.dirname(config.STEPS_VENUES_RAW_CSV), exist_ok=True)

    print(f"Download {config.STEPS_REPO_ID} / {config.STEPS_CHECKINS_FILENAME} ...")
    path = hf_hub_download(repo_id=config.STEPS_REPO_ID,
                            filename=config.STEPS_CHECKINS_FILENAME,
                            repo_type="dataset")
    df = pd.read_csv(path)
    n_before = len(df)
    print(f"Total check-in: {n_before}")

    df = df.dropna(subset=["latitude", "longitude", "name"])
    n_after_dropna = len(df)
    print(f"Setelah drop null lat/lon/name: {n_after_dropna} "
          f"({n_before - n_after_dropna} dibuang, "
          f"{(n_before - n_after_dropna) / n_before:.1%})")

    checkins_path = "data/raw/steps_checkins_raw.csv"
    df.to_csv(checkins_path, index=False)
    print(f"Tersimpan (level check-in) -> {checkins_path}")

    # Agregasi per venue: 1 row/venue, checkin_count = popularitas nyata.
    venues = (
        df.groupby("venue_id")
        .agg(
            name=("name", "first"),
            venue_category=("venue_category", "first"),
            latitude=("latitude", "first"),
            longitude=("longitude", "first"),
            address=("address", "first"),
            checkin_count=("venue_id", "count"),
            last_checkin=("timestamp", "max"),
        )
        .reset_index()
    )
    print(f"Venue unik (sebelum filter kategori): {len(venues)}")

    venues.to_csv(config.STEPS_VENUES_RAW_CSV, index=False)
    print(f"Tersimpan (level venue) -> {config.STEPS_VENUES_RAW_CSV}")


if __name__ == "__main__":
    main()

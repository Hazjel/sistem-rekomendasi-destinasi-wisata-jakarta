"""
Unduh dataset Massive-STEPS-Jakarta (HuggingFace) -- check-in nyata (GPS +
user behavior), pelengkap OSM yang tidak punya data trajectory/popularitas asli.

Tahap ini HANYA download dan simpan mentah -- tidak ada cleaning/transformasi.
Cleaning (drop null, agregasi per venue) dilakukan di 02_preprocessing/clean_steps.py.

Output:
    data/raw/jakarta_checkins_raw.csv  (mentah apa adanya dari HuggingFace, 412.100 row)
"""
import os
import sys

import pandas as pd
from huggingface_hub import hf_hub_download

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def main():
    os.makedirs("data/raw", exist_ok=True)

    print(f"Download {config.STEPS_REPO_ID} / {config.STEPS_CHECKINS_FILENAME} ...")
    path = hf_hub_download(repo_id=config.STEPS_REPO_ID,
                            filename=config.STEPS_CHECKINS_FILENAME,
                            repo_type="dataset")
    df = pd.read_csv(path)
    print(f"Total check-in (mentah): {len(df)}")
    print(f"Kolom: {list(df.columns)}")
    print(f"Null per kolom:")
    print(df.isnull().sum()[df.isnull().sum() > 0].to_string())

    out = "data/raw/jakarta_checkins_raw.csv"
    df.to_csv(out, index=False)
    print(f"\nTersimpan mentah -> {out} ({len(df)} baris)")


if __name__ == "__main__":
    main()

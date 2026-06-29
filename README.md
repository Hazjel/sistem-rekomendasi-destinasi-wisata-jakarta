# Sistem Rekomendasi Destinasi Wisata Jakarta (Multi-Day Itinerary)

Sistem rekomendasi wisata Jakarta berbasis **2 sumber data**:
**Massive-STEPS-Jakarta** (check-in nyata, HuggingFace) sebagai tulang
punggung popularitas & trajectory, **OpenStreetMap (OSM)** sebagai enrichment
(jam buka, link referensi, data hotel). Target akhir: *multi-day itinerary*
hasil **Content-Based Filtering + Clustering** (Fase 1) diikuti **optimasi
rute Genetic Algorithm & PSO** (Fase 2, next phase — lihat catatan di bawah).

> **Catatan etika/legal:** Scraping TripAdvisor TIDAK dipakai (melanggar ToS).
> OSM = *API harvesting* objek terbuka (ODbL). Massive-STEPS = dataset
> penelitian publik (HuggingFace, check-in historis terdeanonimisasi).

## Sumber data

| Sumber | Isi | Peran |
|--------|-----|-------|
| **Massive-STEPS-Jakarta** (HuggingFace) | 412.100 check-in nyata, 71.150 venue, 8.336 user, trajectory/sequence kunjungan | Tulang punggung: POI + popularitas nyata (`checkin_count`) |
| **OSM Overpass** | venue wisata (kategori, jam buka, link) + hotel | Enrichment: lengkapi jam buka/referensi yang Massive-STEPS tak punya, sumber data hotel |

`unique_visitors` & `time_spent` versi OSM-only (pipeline lama) tetap sintetis
(model lognormal per kategori) — **dipakai hanya bila venue tidak match ke
Massive-STEPS**. Versi merged memakai `checkin_count` (popularitas nyata).

### Kolom kunci & sumbernya

| kolom | sumber | keterangan |
|-------|--------|-----------|
| `venue_id`, `name`, `venue_category`, `latitude`, `longitude` | **Massive-STEPS (nyata)** | identitas + lokasi POI hasil check-in nyata |
| `checkin_count` | **Massive-STEPS (nyata)** | jumlah check-in historis = proxy popularitas asli |
| `opening_hours`, `References`, `osm_url` | **OSM (nyata, via merge)** | dilengkapi dari OSM terdekat (radius 150m), kosong bila tak match |
| `hours_source` | derivasi | `osm` = jam nyata, `default` = fallback (tak match OSM) |
| `zone_id` | **derivasi (K-Means)** | cluster geografis, basis scope `time_matrix` |
| `time_spent` | **simulasi** | durasi rata-rata kunjungan **di venue**, menit (sintetis, beda dari time_matrix) |
| `time_matrix` (`duration_minutes`) | **OSRM (rute nyata) / estimasi fallback** | waktu tempuh **antar venue**, menit — dipakai constraint GA/PSO (next phase) |

**Beda `time_spent` vs `time_matrix`:** `time_spent` = berapa lama turis di
*dalam* satu venue (sintetis, profil kategori). `time_matrix` = berapa lama
perjalanan *dari* satu venue *ke* venue lain (OSRM rute jalan asli, fallback
estimasi `jarak/speed` kalau OSRM gagal). Dua hal beda, jangan disamakan.

## Pipeline (per fase riset, selaras `docs/notebooks/`)

```
01_data_collection/
  collect_osm.py      -> data/raw/venues_raw.csv        (harvest venue wisata OSM)
  collect_hotels.py   -> data/raw/hotels_raw.csv         (harvest hotel OSM, utk titik berangkat/pulang)
  collect_steps.py    -> data/raw/steps_venues_raw.csv   (download + agregasi Massive-STEPS-Jakarta)

02_preprocessing/
  enrich.py           -> data/processed/venues_enriched.csv  (jam buka, link, metrik sintetis OSM)
  filter_tourism.py    -> data/processed/steps_filtered.csv   (whitelist 23 kategori wisata)
  merge_sources.py     -> data/processed/merged_venues.csv    (Massive-STEPS + enrichment OSM)
  openhours.py          (parser tag opening_hours -> jam per hari)

03_clustering/
  cluster_zones.py    -> data/processed/clustered_venues.csv (K-Means by lat/lon -> zone_id)

04_time_matrix/
  build_time_matrix.py -> data/processed/time_matrix.csv     (waktu tempuh antar venue, per zone)

05_modeling/           -> PLACEHOLDER, next phase (GA & PSO optimasi rute itinerary)

config.py             -> semua parameter (bbox, filter kategori, OSRM endpoint, dst)
recommend.py / api.py / make_map.py -> tetap di root (rekomendasi single-venue,
                          REST API, viz peta) — next phase diarahkan ke
                          clustered_venues.csv setelah GA/PSO ada
```

**Urut wajib (tiap step baca output sebelumnya):**
`collect_osm`/`collect_hotels`/`collect_steps` → `enrich` (utk OSM) →
`filter_tourism` → `merge_sources` → `cluster_zones` → `build_time_matrix`.

## Cara pakai

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt   # + jupyter/jupytext utk notebook presentasi

python 01_data_collection/collect_osm.py      # harvest venue wisata OSM (butuh internet)
python 01_data_collection/collect_hotels.py   # harvest hotel OSM
python 01_data_collection/collect_steps.py    # download Massive-STEPS-Jakarta
python 02_preprocessing/enrich.py             # enrich venue OSM
python 02_preprocessing/filter_tourism.py     # filter Massive-STEPS ke kategori wisata
python 02_preprocessing/merge_sources.py      # gabung Massive-STEPS + OSM
python 03_clustering/cluster_zones.py         # cluster per zona (K-Means)
python 04_time_matrix/build_time_matrix.py    # waktu tempuh antar venue per zona (OSRM)

python recommend.py        # demo CLI top-10 (pipeline OSM-only lama)
uvicorn api:app --reload   # REST API
```

API:
```
GET /recommend?lat=-6.1754&lon=106.8272&category=tourism:museum&day=Sabtu&top_n=10
GET /health
```

## Notebook presentasi mingguan

`docs/notebooks/` — tiap fase punya notebook ber-output (tabel/grafik sudah
dieksekusi), siap dipresentasikan tanpa alt-tab kode↔slide:

```
02_data_collection.ipynb   -> stats OSM + Massive-STEPS + hotel
03_data_processing.ipynb   -> before/after filter & merge
05_clustering.ipynb        -> scatter per zone_id, kategori dominan per zone
06_time_matrix.ipynb       -> heatmap waktu tempuh, OSRM vs fallback
```

Update notebook: edit source, convert+execute ulang via jupytext —
```powershell
jupytext --to ipynb --set-kernel jakarta-wisata-venv --execute docs/notebooks/NAMA.py
```

## Engine rekomendasi (pipeline OSM-only, `recommend.py`)

```
score = 0.30*similarity_konten + 0.35*kedekatan_geo
      + 0.20*popularitas + 0.15*buka_di_hari_terpilih
```

- **similarity_konten**: TF-IDF kategori + cosine similarity terhadap minat user.
- **kedekatan_geo**: haversine jarak turis→venue, dinormalisasi (dekat = tinggi).
- **popularitas**: `unique_visitors` ternormalisasi (sintetis, pipeline OSM-only).
- **buka_di_hari**: 1 jika venue buka di hari terpilih, 0 jika tutup.

Cold-start friendly — tak butuh riwayat user. Ini **belum** itinerary
multi-day — itu target akhir riset (Fase 2: GA/PSO, next phase).

## Next phase (belum dikerjakan)

- **GA & PSO**: optimasi urutan kunjungan venue (multi-day itinerary) memakai
  `time_matrix` sebagai constraint waktu tempuh + `time_spent` sebagai durasi
  kunjungan, fitness = minimasi total waktu + maksimasi rating/popularitas.
- **UI website**: input hotel (titik berangkat/pulang) — data hotel sudah
  disiapkan (`hotels_raw.csv`), integrasi ke `api.py`/frontend itinerary
  builder menyusul setelah GA/PSO punya output untuk diuji.
- Evaluasi user satisfaction / metrik konvergensi optimizer (GA vs PSO).

## Metode (untuk laporan riset)

- Jenis: *secondary data collection* (Massive-STEPS, dataset penelitian publik)
  + *API harvesting* (OSM, bukan web scraping) + *purposive/criterion-based
  sampling* (kriteria = kategori wisata dalam batas geografis Jakarta).
- Limitasi:
  - `unique_visitors`/`time_spent` versi OSM-only sintetis (lognormal per
    kategori) — dipakai hanya untuk venue yang tak match Massive-STEPS.
  - `time_matrix` dari OSRM **tanpa traffic real-time** (estimasi rute jalan
    statis); fallback estimasi (`jarak/speed`) kalau OSRM gagal/timeout.
  - Massive-STEPS data historis (2012–2018), bukan real-time.
  - `merge_sources` matching by koordinat (radius 150m) — venue yang
    koordinatnya jauh dari OSM (>150m) tidak terlengkapi jam buka/referensi.

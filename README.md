# Sistem Rekomendasi Destinasi Wisata Jakarta (Multi-Day Itinerary)

Riset program **HUMIC** — sistem rekomendasi wisata Jakarta multi-hari berbasis
**Content-Based Filtering + Clustering + optimasi rute Genetic Algorithm & PSO**.

> **Etika/Legal:** OSM = API harvesting objek terbuka (ODbL). Massive-STEPS =
> dataset penelitian publik (HuggingFace). Scraping TripAdvisor **tidak dipakai**
> (melanggar ToS). Google Places API dipakai dengan key pribadi (env var).

---

## Sumber Data

| Sumber | Isi | Peran |
|--------|-----|-------|
| **Massive-STEPS-Jakarta** (HuggingFace) | 412.100 check-in nyata, 8.336 user, 2012–2018 | POI + popularitas nyata (`checkin_count`) |
| **OpenStreetMap (Overpass)** | venue wisata, batas wilayah DKI | Koordinat + kategori awal |
| **Google Places API (New)** | jam buka, alamat, deskripsi, rating | Enrichment jam buka & data detail |
| **Wikipedia REST API** | deskripsi venue | Enrichment deskripsi untuk Content-Based Filtering |
| **OSRM** (`router.project-osrm.org`) | waktu tempuh rute jalan | Time matrix antar venue |
| **Manual** (`data/raw/manual_venues.csv`) | venue valid tidak tertangkap pipeline otomatis | Tambahan idempoten via `merge_google_venues.py` |

---

## Dataset Final (per 2026-07-02) — Valid, Siap Pakai

| File | Isi | Keterangan |
|------|-----|-----------|
| `data/processed/jakarta_tourism_venues.csv` | **219 venue**, tanpa zone_id | Share ke rekan / input Content-Based Filtering |
| `data/processed/jakarta_tourism_venues_clustered.csv` | 219 venue + `zone_id` + `time_spent_minutes` | Input GA/PSO + visualisasi cluster |
| `data/processed/jakarta_travel_time_inzone.csv` | **3.919 pasangan** in-zone (100% OSRM) | Fitness penalty in-zone untuk GA/PSO |
| `data/processed/jakarta_travel_time_allpairs.csv` | **23.871 pasangan** all-pairs (100% OSRM) | Lookup cross-zone untuk GA/PSO |
| `data/processed/jakarta_hotels.csv` | **181 hotel** bersih (daratan Jakarta) | Titik berangkat/pulang itinerary |

### Kolom Kunci Dataset Venue

| Kolom | Sumber | Keterangan |
|-------|--------|-----------|
| `venue_id`, `name`, `venue_category` | Massive-STEPS / OSM | Identitas POI |
| `latitude`, `longitude` | OSM / Google Places (fix via `fix_audit_issues.py`) | Koordinat terverifikasi |
| `checkin_count` | Massive-STEPS | Popularitas nyata (proxy) |
| `google_rating`, `google_rating_count` | Google Places API | Rating publik |
| `{Hari}_buka`, `{Hari}_tutup` | Google Places API / web / default | Jam buka per hari (14 kolom) |
| `hours_source` | derivasi | `google_places` / `web_search` / `default_category` |
| `time_spent_minutes` | formula log10(rating_count) — Lim 2019 | Estimasi durasi kunjungan |
| `description` | Wikipedia REST API | Untuk TF-IDF Content-Based Filtering |
| `address` | Google Places API | Backfill via `enrich_address_google.py` |
| `zone_id` | K-Means k=8 (scikit-learn) | Cluster geografis, hanya di file `_clustered` |

---

## Pipeline (Urutan Wajib, Semua Scripted)

```
01_data_collection/
  collect_osm.py              → data/raw/venues_osm_raw.csv
  collect_steps.py            → download Massive-STEPS dari HuggingFace
  collect_hotels_google.py    → data/processed/hotels_google.csv (raw)
  collect_venues_google.py    → data/raw/venues_google_raw.csv

02_preprocessing/
  clean_steps.py              → filter STEPS ke kategori wisata
  clean_osm.py                → venues_osm_clean.csv
  fill_default_hours.py       → jam default per kategori
  merge_sources.py            → merge OSM + STEPS
  enrich_hours_google.py      → jam buka via Google Places API → merged_venues_enriched.csv
  merge_google_venues.py      → tambah venue Google + manual_venues.csv (idempoten)
  patch_hours_websearch.py    → patch jam 11 venue dari sumber resmi
  fix_audit_issues.py         → hapus noise, fix koordinat, re-enrich jam
  clean_merged.py             → blacklist + polygon DKI + business_status
  enrich_address_google.py    → backfill address via Google Places
  enrich_description_wikipedia.py → backfill description via Wikipedia
  add_time_spent.py           → kolom time_spent_minutes
  clean_hotels.py             → hotels_google.csv → jakarta_hotels.csv

03_clustering/
  cluster_zones.py            → jakarta_tourism_venues_clustered.csv (K-Means k=8)
                                 jakarta_tourism_venues.csv (tanpa zone_id)

04_time_matrix/
  build_time_matrix.py        → jakarta_travel_time_inzone.csv (in-zone, OSRM)
  build_time_matrix_allpairs.py → jakarta_travel_time_allpairs.csv (all-pairs, OSRM)

05_modeling/                  ← NEXT PHASE (GA & PSO)
```

---

## Cara Pakai

### Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Buat file `.env` di root (jangan di-commit):
```
GOOGLE_PLACES_KEY=your_api_key_here
```

### Jalankan Pipeline (full rebuild)

```powershell
# 01 — Koleksi data
python 01_data_collection/collect_osm.py
python 01_data_collection/collect_steps.py
python 01_data_collection/collect_hotels_google.py
python 01_data_collection/collect_venues_google.py

# 02 — Preprocessing
python 02_preprocessing/clean_steps.py
python 02_preprocessing/clean_osm.py
python 02_preprocessing/fill_default_hours.py
python 02_preprocessing/merge_sources.py
python 02_preprocessing/enrich_hours_google.py
python 02_preprocessing/merge_google_venues.py
python 02_preprocessing/patch_hours_websearch.py
python 02_preprocessing/fix_audit_issues.py
python 02_preprocessing/clean_merged.py
python 02_preprocessing/enrich_address_google.py
python 02_preprocessing/enrich_description_wikipedia.py
python 02_preprocessing/add_time_spent.py
python 02_preprocessing/clean_hotels.py

# 03 — Clustering
python 03_clustering/cluster_zones.py

# 04 — Time matrix (lama, butuh koneksi OSRM)
python 04_time_matrix/build_time_matrix.py
python 04_time_matrix/build_time_matrix_allpairs.py
```

---

## Keputusan Teknis

| Keputusan | Alasan |
|-----------|--------|
| **Mall tidak masuk** | Scope riset = destinasi wisata (atraksi/budaya/alam). Mall = belanja, bukan destinasi. |
| **K-Means k=8** (Euclidean lat/lon) | Cluster geografis untuk inisialisasi populasi GA/PSO dan soft constraint cross-zone. |
| **OSRM tanpa traffic** | Tidak ada realtime traffic di OSRM public demo — limitasi dideklarasi di laporan. |
| **time_spent via log10** | Formula Lim 2019: `log10(rating_count)` × faktor kategori. Proxy, bukan empiris. |
| **Soft clustering** | `zone_id` = penalti cross-zone di fitness function, bukan hard constraint. User bebas pilih venue lintas zone. |
| **manual_venues.csv** | Venue valid tidak tertangkap pipeline otomatis. Dibaca idempoten oleh `merge_google_venues.py`. |

---

## Limitasi (untuk Laporan)

- OSRM tanpa realtime traffic — tidak memperhitungkan kemacetan Jakarta
- Massive-STEPS historis 2012–2018 — popularitas bisa berubah
- `time_spent_minutes` berbasis formula, bukan observasi langsung per venue
- K-Means zona ≠ zona administratif Jakarta

---

## Next Phase (Belum Dikerjakan)

**`05_modeling/` — GA & PSO optimasi rute itinerary multi-hari**

- Input: `jakarta_tourism_venues_clustered.csv` + `jakarta_travel_time_allpairs.csv` + `jakarta_hotels.csv`
- Constraint TTDP: `arrival_time + time_spent_minutes ≤ closing_time`
- Fitness: maximize satisfaction − penalti_waktu − penalti_cross_zone (soft)
- Evaluasi: konvergensi GA vs PSO, silhouette score clustering

**Content-Based Filtering** — TF-IDF dari `description` + `venue_category`

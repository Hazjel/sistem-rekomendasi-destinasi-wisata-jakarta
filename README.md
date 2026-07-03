# Sistem Rekomendasi Destinasi Wisata Jakarta (Multi-Day Itinerary)

Riset program **HUMIC** — sistem rekomendasi wisata Jakarta multi-hari berbasis
**Content-Based Filtering + Clustering + optimasi rute Genetic Algorithm & PSO**.

> Pipeline dijalankan dari notebook `docs/notebooks/` (urut 01→05). Lihat [PIPELINE.md](PIPELINE.md).

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

## Dataset Final (per 2026-07-03) — Valid, Siap Pakai

| File | Isi | Keterangan |
|------|-----|-----------|
| `data/processed/jakarta_tourism_venues.csv` | **226 venue**, tanpa zone_id | Share ke rekan / input Content-Based Filtering |
| `data/processed/jakarta_tourism_venues_clustered.csv` | 226 venue + `zone_id` + `time_spent_minutes` | Input GA/PSO + visualisasi cluster |
| `data/processed/jakarta_travel_time_inzone.csv` | **4.158 pasangan** in-zone (100% OSRM) | Fitness penalty in-zone untuk GA/PSO |
| `data/processed/jakarta_travel_time_allpairs.csv` | **25.425 pasangan** all-pairs (100% OSRM) | Lookup cross-zone untuk GA/PSO |
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

## Pipeline (Jalankan via Notebook, Urut)

Semua fase dijalankan dari **notebook** di `docs/notebooks/`. Tiap notebook =
1 fase; jalankan sel `[RUN]` urut atas→bawah. Semua sel **cache-aware** (skip
kalau output sudah ada — hapus file output untuk rebuild).

```
docs/notebooks/
  01_data_collection.ipynb   → data/raw/*  + hotels_google.csv
      Kode collection inline (OSM Overpass, STEPS HuggingFace, Google Places).

  02_preprocessing_pipeline.ipynb → merged_venues_enriched.csv (226 venue)
      13 step. Sel [RUN] memanggil script Preprocessing/*.py via run_step()
      (output streaming real-time ke notebook). Script enrichment API tetap .py.

  03_clustering.ipynb        → jakarta_tourism_venues_clustered.csv (K-Means k=8)
                               jakarta_tourism_venues.csv (tanpa zone_id)
      Kode clustering inline.

  04_time_matrix.ipynb       → jakarta_travel_time_inzone.csv (4.158 pasangan)
                               jakarta_travel_time_allpairs.csv (25.425 pasangan)
      Kode OSRM inline. Butuh koneksi internet.

  05_modeling.ipynb          → prototipe engine rekomendasi hybrid (06_api/)
```

Folder pendukung (bukan dijalankan langsung):

```
Preprocessing/   15 script .py — dipanggil NB 02 via subprocess.
                    dki_boundary.py = helper polygon (diimport, bukan step).
                    archive/ = script satu-kali, bukan pipeline aktif.
05_modeling/        ← NEXT PHASE (GA & PSO), belum ada isi.
06_api/             recommend.py / api.py / make_map.py — prototipe API.
config.py           konstanta bersama (path, blacklist, kategori) — di-import.
```

> **Catatan**: fase collection/clustering/time_matrix kodenya **inline penuh** di
> notebook (tidak ada folder script terpisah). Hanya preprocessing yang menyimpan
> `.py` terpisah (dipanggil via subprocess) karena logic enrichment API panjang &
> one-time.

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

Buka `docs/notebooks/` di Jupyter, jalankan urut:

1. **`01_data_collection.ipynb`** — sel `[RUN]` harvest OSM + download STEPS +
   Google Places (butuh internet + `GOOGLE_PLACES_KEY`).
2. **`02_preprocessing_pipeline.ipynb`** — sel `[RUN]` step 1→13 (memanggil
   `Preprocessing/*.py`, output streaming di notebook).
3. **`03_clustering.ipynb`** — sel `[RUN]` clustering K-Means.
4. **`04_time_matrix.ipynb`** — sel `[RUN]` in-zone + all-pairs OSRM (butuh internet).

Tiap sel `[RUN]` skip otomatis kalau output sudah ada. Untuk rebuild dari nol,
hapus file output terkait di `data/processed/` lalu jalankan ulang.

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

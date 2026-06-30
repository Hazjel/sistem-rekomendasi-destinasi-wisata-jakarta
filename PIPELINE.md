# Pipeline ETL — Sistem Rekomendasi Destinasi Wisata Jakarta

Jalankan script **berurutan** sesuai nomor folder. Tiap folder = 1 fase.

---

## 01 — Data Collection (`01_data_collection/`)

Output ke `data/raw/` — **zero cleaning**, data mentah apa adanya.

| Script | Output | Keterangan |
|--------|--------|-----------|
| `collect_osm.py` | `data/raw/venues_osm_raw.csv` | Venue wisata dari OpenStreetMap Overpass API, boundary DKI Jakarta admin_level=4 |
| `collect_steps.py` | `data/raw/jakarta_checkins_raw.csv` | 412.100 check-in nyata dari Massive-STEPS-Jakarta (HuggingFace) |
| `collect_venues_google.py` | `data/raw/venues_google_raw.csv` | Venue wisata tambahan via Google Places Nearby Search (12 kategori x 21 anchor) |
| `collect_hotels_google.py` | `data/processed/hotels_google.csv` | 280 hotel/penginapan via Google Places (titik start/end itinerary) |

Butuh env var: `GOOGLE_PLACES_KEY`

---

## 02 — Preprocessing (`02_preprocessing/`)

Transformasi bertahap. Tiap script punya print **before/after** jumlah row.

| Urutan | Script | Input | Output | Keterangan |
|--------|--------|-------|--------|-----------|
| 1 | `clean_osm.py` | `venues_osm_raw.csv` | `venues_osm_clean.csv` | Dedupe exact + cluster-dedupe venue besar (Monas, dll) |
| 2 | `clean_steps.py` | `jakarta_checkins_raw.csv` | `steps_checkins_clean.csv` + `steps_venues_raw.csv` | Drop null, agregasi per venue, hitung checkin_count |
| 3 | `filter_tourism.py` | `steps_venues_raw.csv` | `steps_filtered.csv` | 4 tahap: whitelist 14 kategori → keyword-exclude → blacklist eksplisit → dedupe nama |
| 4 | `merge_sources.py` | `steps_filtered.csv` | `merged_venues.csv` | Gabung Massive-STEPS + OSM enrichment radius 150m |
| 5 | `enrich_hours_google.py` | `merged_venues.csv` | `merged_venues_enriched.csv` | Enrich jam buka + 10 field Google Places. Fallback jam default per kategori jika tidak ditemukan |
| 6 | `patch_address_cache.py` | cache + `merged_venues_enriched.csv` | `merged_venues_enriched.csv` | Backfill sublocality/locality dari addressComponents (administrative_area_level_4/2) |
| 7 | `merge_google_venues.py` | `venues_google_raw.csv` + `merged_venues_enriched.csv` | `merged_venues_enriched.csv` | Tambah venue dari Google batch. Filter polygon DKI (bukan bbox) |
| 8 | `retry_missing_venues.py` | `merged_venues_enriched.csv` | `merged_venues_enriched.csv` | Retry Google Places dengan query alternatif untuk venue yang masih default_category |
| 9 | `clean_merged.py` | `merged_venues_enriched.csv` | `merged_venues_enriched.csv` | Filter: blacklist, luar polygon DKI, businessStatus CLOSED, temple/vihara kecil (checkin<5) |

**Result setelah 02**: `data/processed/merged_venues_enriched.csv` — ~255 venue OPERATIONAL DKI Jakarta, lengkap jam buka per hari, google_rating, businessStatus, sublocality, aksesibilitas, dll.

---

## 03 — Clustering (`03_clustering/`)

| Script | Input | Output | Keterangan |
|--------|-------|--------|-----------|
| `cluster_zones.py` | `merged_venues_enriched.csv` | `clustered_venues.csv` | K-Means k=8 by lat/lon → zone_id (0-7) untuk scope time matrix |

---

## 04 — Time Matrix (`04_time_matrix/`)

| Script | Input | Output | Keterangan |
|--------|-------|--------|-----------|
| `build_time_matrix.py` | `clustered_venues.csv` | `time_matrix.csv` | Waktu tempuh OSRM antar venue dalam zona yang sama (bukan lintas zona) |

Waktu tempuh = **travel time** antar venue. Beda dari `time_spent` (durasi **di** venue, parameter GA/PSO).

---

## 05 — Modeling (`05_modeling/`)

**Belum diimplementasi.** Rencana:
- GA (Genetic Algorithm) optimasi urutan kunjungan multi-hari
- PSO (Particle Swarm Optimization) sebagai pembanding
- Constraint: `time_matrix` + `time_spent` + jam buka + `price_level` + `good_for_children`
- Evaluasi: konvergensi, user satisfaction score

---

## 06 — API & Visualisasi (`06_api/`)

| Script | Keterangan |
|--------|-----------|
| `recommend.py` | Engine rekomendasi hybrid (TF-IDF + geo + google_rating + jam buka) |
| `api.py` | REST API FastAPI — `GET /recommend?lat=...&lon=...&day=Sabtu` |
| `make_map.py` | Generate peta interaktif HTML semua venue |

Jalankan API: `uvicorn 06_api.api:app --reload` dari root project.

---

## Data flow ringkasan

```
data/raw/
  venues_osm_raw.csv          ← collect_osm.py
  jakarta_checkins_raw.csv    ← collect_steps.py
  venues_google_raw.csv       ← collect_venues_google.py

data/processed/
  venues_osm_clean.csv        ← clean_osm.py
  steps_checkins_clean.csv    ← clean_steps.py
  steps_venues_raw.csv        ← clean_steps.py
  steps_filtered.csv          ← filter_tourism.py
  merged_venues.csv           ← merge_sources.py
  merged_venues_enriched.csv  ← enrich_hours_google.py → clean_merged.py → merge_google_venues.py
  clustered_venues.csv        ← cluster_zones.py
  time_matrix.csv             ← build_time_matrix.py
  hotels_google.csv           ← collect_hotels_google.py
```

# Pipeline ETL — Sistem Rekomendasi Destinasi Wisata Jakarta

Semua fase dijalankan dari **notebook** di `docs/notebooks/`, urut per nomor.
Tiap sel `[RUN]` **cache-aware** (skip kalau output ada). Dataset final:
**219 venue, 181 hotel**. `config.py` = konstanta bersama (path, blacklist,
kategori) — di-import semua notebook.

---

## NB 01 — Data Collection (`docs/notebooks/01_data_collection.ipynb`)

Kode collection **inline penuh** di notebook (tidak ada folder script terpisah).

| Sumber | Output | Keterangan |
|--------|--------|-----------|
| OSM Overpass | `data/raw/venues_osm_raw.csv` | Venue wisata boundary DKI admin_level=4 |
| Massive-STEPS (HuggingFace) | `data/raw/jakarta_checkins_raw.csv` | 412.100 check-in nyata |
| Google Places venue | `data/raw/venues_google_raw.csv` | 12 kategori × 21 anchor |
| Google Places hotel | `data/processed/hotels_google.csv` | 280 hotel raw |

Butuh: internet + `GOOGLE_PLACES_KEY`. Cache Google di `google_venues_cache/`,
`google_hotel_cache/`.

---

## NB 02 — Preprocessing (`docs/notebooks/02_preprocessing_pipeline.ipynb`)

13 step. Sel `[RUN]` memanggil script `Preprocessing/*.py` via `run_step()`
(output streaming real-time ke notebook — before/after tetap terdokumentasi).
Script enrichment API tetap `.py`: one-time, butuh API key + cache.

| # | Script | Input | Output |
|---|--------|-------|--------|
| 1 | `clean_steps.py` | `jakarta_checkins_raw.csv` | `steps_checkins_clean.csv` + `steps_venues_raw.csv` |
| 2 | `clean_osm.py` | `venues_osm_raw.csv` | `venues_osm_clean.csv` (dedupe + cluster-dedupe, self-contained) |
| 3 | `filter_tourism.py` | `steps_venues_raw.csv` | `steps_filtered.csv` (whitelist 14 kategori) |
| 4 | `merge_sources.py` | `steps_filtered.csv` + `venues_osm_clean.csv` | `merged_venues.csv` |
| 5 | `enrich_hours_google.py` + `fill_default_hours.py` | `merged_venues.csv` | `merged_venues_enriched.csv` (jam nyata + rating + description) |
| 6 | `merge_google_venues.py` | `venues_google_raw.csv` + `manual_venues.csv` | tambah venue Google + manual (idempoten) |
| 7 | `patch_hours_websearch.py` | `merged_venues_enriched.csv` | patch jam 11 venue sumber resmi |
| 8 | `fix_audit_issues.py` | `merged_venues_enriched.csv` | hapus noise, fix koordinat |
| 9 | `clean_merged.py` | `merged_venues_enriched.csv` | blacklist + polygon DKI + businessStatus |
| 10 | `enrich_address_google.py` | `merged_venues_enriched.csv` | backfill address |
| 11 | `enrich_description_wikipedia.py` | `merged_venues_enriched.csv` | backfill description (TF-IDF) |
| 12 | `add_time_spent.py` | `merged_venues_enriched.csv` | kolom `time_spent_minutes` |
| 13 | `clean_hotels.py` | `hotels_google.csv` | `jakarta_hotels.csv` (181 hotel) |

`dki_boundary.py` = helper polygon DKI (diimport step 9 & 6, bukan step).
`archive/` = script satu-kali, bukan pipeline aktif.

**Result**: `merged_venues_enriched.csv` — **219 venue** OPERATIONAL DKI, lengkap
jam per hari, google_rating, description, address, time_spent_minutes.

---

## NB 03 — Clustering (`docs/notebooks/03_clustering.ipynb`)

Kode K-Means **inline**. Input `merged_venues_enriched.csv` →
`jakarta_tourism_venues_clustered.csv` (+zone_id) & `jakarta_tourism_venues.csv`
(tanpa zone_id). K-Means k=8 by lat/lon → soft constraint cross-zone GA/PSO.

---

## NB 04 — Time Matrix (`docs/notebooks/04_time_matrix.ipynb`)

Kode OSRM **inline**. Butuh internet.

| Output | Isi |
|--------|-----|
| `jakarta_travel_time_inzone.csv` | 3.912 pasangan in-zone (zone sama) |
| `jakarta_travel_time_allpairs.csv` | 23.871 pasangan all-pairs (nC2) |

100% OSRM, 0 fallback. In-zone = fitness penalty; all-pairs = lookup cross-zone.

---

## NB 05 — Modeling prototipe (`docs/notebooks/05_modeling.ipynb`)

Prototipe engine rekomendasi hybrid `06_api/recommend.py` (TF-IDF + geo + rating +
jam). **Bukan** GA/PSO final — itu next phase di `05_modeling/`.

---

## NB 06 — Optimasi Itinerary (`docs/notebooks/06_optimization.ipynb`) + `05_modeling/`

FASE MODELING (selesai): CBF (TF-IDF) + 3 algoritma optimasi dibandingkan.

| Modul | Isi |
|-------|-----|
| `05_modeling/cbf.py` | TF-IDF + cosine + Bayesian weighted rating + filter budget (proxy kategori) |
| `05_modeling/problem.py` | TTDP: time-budget decoding + fitness (satisfaction − travel − cross_zone − penalti jam) |
| `05_modeling/ga.py` | GA: OX crossover, tournament, swap mutation, elitism |
| `05_modeling/pso.py` | PSO diskrit swap-sequence |
| `05_modeling/hybrid.py` | GA-PSO hybrid (PSO + refresh genetik) |
| `05_modeling/experiment.py` | runner 3 skenario × 3 algoritma × 10 run → `optimization_results.csv` + `optimization_convergence.csv` |

Input: clustered + allpairs + hotels. Konstanta di `config.py` (bagian FASE MODELING).
NB 06 = demo input turis → itinerary + peta folium + kurva konvergensi + tabel USS.
Silhouette score clustering ada di NB 03.

---

## 06_api — Prototipe API

| Script | Input | Keterangan |
|--------|-------|-----------|
| `recommend.py` | `merged_venues_enriched.csv` | Engine rekomendasi hybrid |
| `api.py` | — | REST API FastAPI — `GET /recommend?lat=...&lon=...&day=Sabtu` |
| `make_map.py` | `jakarta_tourism_venues_clustered.csv` | Peta interaktif HTML |

Jalankan API: `uvicorn 06_api.api:app --reload` dari root.

---

## Data flow ringkasan

```
data/raw/
  venues_osm_raw.csv          ← NB 01
  jakarta_checkins_raw.csv    ← NB 01
  venues_google_raw.csv       ← NB 01
  manual_venues.csv           (manual)

data/processed/
  hotels_google.csv           ← NB 01
  steps_checkins_clean.csv    ← NB 02 step 1
  steps_venues_raw.csv        ← NB 02 step 1
  venues_osm_clean.csv        ← NB 02 step 2
  steps_filtered.csv          ← NB 02 step 3
  merged_venues.csv           ← NB 02 step 4
  merged_venues_enriched.csv  ← NB 02 step 5-12
  jakarta_tourism_venues.csv           ← NB 03
  jakarta_tourism_venues_clustered.csv ← NB 03
  jakarta_travel_time_inzone.csv       ← NB 04
  jakarta_travel_time_allpairs.csv     ← NB 04
  jakarta_hotels.csv                   ← NB 02 step 13
```

> **Catatan**: `data/` di-gitignore — di-generate ulang via notebook, tidak
> di-commit. Dataset final = 6 file yang dipakai fase modeling
> (venues, clustered, inzone, allpairs, hotels, merged_venues_enriched).

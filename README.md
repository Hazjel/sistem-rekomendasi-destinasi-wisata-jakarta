# Sistem Rekomendasi Destinasi Wisata Jakarta (Multi-Day Itinerary)

Riset program **HUMIC** — sistem rekomendasi wisata Jakarta multi-hari berbasis
**Content-Based Filtering + Clustering + optimasi rute Genetic Algorithm & PSO**.

> Pipeline dijalankan dari notebook `notebooks/` (urut 01→06). Lihat [PIPELINE.md](PIPELINE.md).

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
| `data/processed/jakarta_tourism_venues.csv` | **163 venue**, tanpa zone_id | Share ke rekan / input Content-Based Filtering |
| `data/processed/jakarta_tourism_venues_clustered.csv` | 163 venue + `zone_id` + `time_spent_minutes` | Input GA/PSO + visualisasi cluster |
| `data/processed/jakarta_travel_time_inzone.csv` | **2.301 pasangan** in-zone (100% OSRM) | Fitness penalty in-zone untuk GA/PSO |
| `data/processed/jakarta_travel_time_allpairs.csv` | **13.203 pasangan** all-pairs (100% OSRM) | Lookup cross-zone untuk GA/PSO |
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

Semua fase dijalankan dari **notebook** di `notebooks/`. Tiap notebook =
1 fase; jalankan sel `[RUN]` urut atas→bawah. Semua sel **cache-aware** (skip
kalau output sudah ada — hapus file output untuk rebuild).

```
notebooks/
  01_data_collection.ipynb   → data/raw/*  + hotels_google.csv
      Kode collection inline (OSM Overpass, STEPS HuggingFace, Google Places).

  02_preprocessing_pipeline.ipynb → merged_venues_enriched.csv (163 venue)
      13 step. Sel [RUN] memanggil script src/preprocessing/*.py via run_step()
      (output streaming real-time ke notebook). Script enrichment API tetap .py.

  03_clustering.ipynb        → jakarta_tourism_venues_clustered.csv (K-Means k=8)
                               jakarta_tourism_venues.csv (tanpa zone_id)
      Kode clustering inline.

  04_time_matrix.ipynb       → jakarta_travel_time_inzone.csv (2.301 pasangan)
                               jakarta_travel_time_allpairs.csv (13.203 pasangan)
      Kode OSRM inline. Butuh koneksi internet.

  05_modeling.ipynb          → FASE 1 MODELING: Content-Based Filtering
                               (TF-IDF + Bayesian rating + filter budget)

  06_optimization.ipynb      → FASE MODELING: CBF + GA vs PSO vs GA-PSO Hybrid
                               demo input turis → itinerary multi-hari + peta,
                               eksperimen 3 skenario × 3 algoritma × 10 run
```

Folder pendukung (bukan dijalankan langsung):

```
src/preprocessing/   15 script .py — dipanggil NB 02 via subprocess.
                    dki_boundary.py = helper polygon (diimport, bukan step).
                    archive/ = script satu-kali, bukan pipeline aktif.
src/modeling/     FASE MODELING (dipanggil NB 06):
                    cbf.py      — TF-IDF + cosine + Bayesian rating + filter budget
                    problem.py  — TTDP: decoding time-budget + fitness
                    ga.py / pso.py / hybrid.py — 3 algoritma optimasi (manual numpy)
                    experiment.py — runner perbandingan → optimization_results.csv
src/api/             recommend.py / api.py / make_map.py — prototipe API.
config.py           konstanta bersama (path, blacklist, kategori, param modeling).
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

Buka `notebooks/` di Jupyter, jalankan urut:

1. **`01_data_collection.ipynb`** — sel `[RUN]` harvest OSM + download STEPS +
   Google Places (butuh internet + `GOOGLE_PLACES_KEY`).
2. **`02_preprocessing_pipeline.ipynb`** — sel `[RUN]` step 1→13 (memanggil
   `src/preprocessing/*.py`, output streaming di notebook).
3. **`03_clustering.ipynb`** — sel `[RUN]` clustering K-Means.
4. **`04_time_matrix.ipynb`** — sel `[RUN]` in-zone + all-pairs OSRM (butuh internet).

Tiap sel `[RUN]` skip otomatis kalau output sudah ada. Untuk rebuild dari nol,
hapus file output terkait di `data/processed/` lalu jalankan ulang.

---

## Keputusan Teknis

| Keputusan | Alasan |
|-----------|--------|
| **Mall tidak masuk** | Scope riset = destinasi wisata (atraksi/budaya/alam). Mall = belanja, bukan destinasi. |
| **Sub-venue TMII dilebur ke induk** | 43 sub-venue (anjungan, museum kecil, wahana) dalam TMII = satu tiket satu kunjungan — itinerary cukup menjadwalkan "TMII". Ancol TIDAK dilebur: Dufan/SeaWorld dkk bertiket terpisah + durasi panjang = destinasi mandiri. Geofence `config.TMII_BBOX` di `clean_merged.py`. |
| **Dedupe audit deskripsi** | 12 entri duplikat/sub-venue dibuang (mis. "Dufan Ancol" dup DUFAN, "Klenteng Petak Sembilan" = nama lain Wihara Dharma Bhakti, kompleks Lubang Buaya dilebur ke Monumen Pancasila Sakti) + 6 deskripsi salah-tempel dikosongkan (anti kontaminasi TF-IDF). Daftar di `clean_merged.py`. |
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

## Fase Modeling (SELESAI — `src/modeling/` + NB 06)

**CBF (TF-IDF) + GA vs PSO vs GA-PSO Hybrid untuk TTDP multi-hari**

- FASE 1 — CBF: TF-IDF `venue_category+description` + Bayesian weighted rating
  + filter budget (proxy kategori) + **seleksi MMR** (diversity — cegah kandidat
  didominasi venue kembar spt 21 Anjungan TMII) → kandidat top-N + satisfaction
- FASE 2 — Optimasi: permutasi kandidat + time-budget decoding (mulai/selesai
  di hotel, cek jam buka per hari, **istirahat makan siang 60 mnt otomatis**
  window 11:30–13:30). Constraint jam tutup **hard** — venue yang bakal
  melanggar ditunda ke hari lain, itinerary output selalu valid.
  Fitness = Σsatisfaction − w·travel − w·cross_zone − w·zone_revisit
  (penalti bolak-balik ke zona yang sudah ditinggal, intra-hari)
  − w·zone_revisit_day (zona kebelah lintas hari) − penalti jam
- 3 algoritma manual numpy: GA (OX + tournament + elitism), PSO diskrit
  (swap-sequence), GA-PSO Hybrid (PSO + refresh genetik) — semuanya di-polish
  **2-opt local search** di akhir (hapus pola rute bolak-balik lokal)
- Evaluasi: konvergensi (10 run ± std), **User Satisfaction Score** kuantitatif,
  runtime, silhouette clustering (NB 03)
- Hasil: lihat `data/processed/optimization_results.csv` + kesimpulan NB 06

**Next**: web app prototipe (extend `src/api` — `POST /itinerary`), feedback loop
bobot fitness, laporan/paper.

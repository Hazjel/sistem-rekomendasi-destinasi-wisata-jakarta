# Sistem Rekomendasi Destinasi Wisata Jakarta

Sistem rekomendasi **hybrid** (content-based + geo + popularitas + jam buka)
untuk destinasi wisata di Jakarta. Data venue dari **OpenStreetMap (OSM)**
via Overpass API — gratis, legal, lisensi **ODbL**.

> **Catatan etika/legal:** Scraping TripAdvisor TIDAK dipakai (melanggar ToS).
> Pengumpulan data = *API harvesting* objek terbuka OSM, bukan scraping HTML.

## Sumber data tiap kolom

| kolom | sumber | keterangan |
|-------|--------|-----------|
| `venue_id`, `name`, `venue_category`, `latitude`, `longitude` | **OSM (nyata)** | identitas + lokasi POI |
| `{Hari}_buka`, `{Hari}_tutup` | **OSM `opening_hours` (nyata)** | jam buka/tutup tiap hari; `"Tutup"` jika libur |
| `hours_source` | derivasi | `osm` = jam nyata, `default` = fallback per kategori (tag kosong) |
| `References` | **OSM (nyata)** | link sumber: `website` > `wikipedia` > `wikidata` > Google Maps |
| `osm_url`, `maps_url` | **OSM (nyata)** | halaman objek OSM + pin Google Maps (deep-link koordinat) |
| `unique_visitors` | **simulasi** | pengunjung unik/minggu (proxy popularitas, sintetis) |
| `time_spent` | **simulasi** | durasi rata-rata kunjungan, satuan **menit** (sintetis) |

Kolom hari = 14 kolom: `Senin_buka`, `Senin_tutup`, `Selasa_buka`, ... `Minggu_tutup`.

`unique_visitors` & `time_spent` sintetis karena metrik traffic bersifat privat
platform dan tak tersedia di API publik. Dibangkitkan model probabilistik
(lognormal) berbasis profil kategori. **Wajib dideklarasi sebagai limitasi riset.**

## Pipeline

```
collect.py   -> data/venues_raw.csv        (harvest POI + tag dari OSM Overpass)
enrich.py    -> data/venues_enriched.csv   (parse jam buka, link, metrik sintetis)
recommend.py -> engine rekomendasi hybrid (library + demo CLI)
api.py       -> REST endpoint (FastAPI)
openhours.py -> parser tag OSM opening_hours -> jam per hari
config.py    -> parameter (bbox Jakarta, filter kategori, endpoint)
```

**Urut wajib:** `collect` → `enrich` → `recommend`/`api` (tiap step baca output sebelumnya).

## Cara pakai

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

python collect.py          # harvest OSM -> venues_raw.csv (butuh internet)
python enrich.py           # -> venues_enriched.csv
python recommend.py        # demo CLI top-10
uvicorn api:app --reload   # REST API
```

API:
```
GET /recommend?lat=-6.1754&lon=106.8272&category=tourism:museum&day=Sabtu&top_n=10
GET /health
```

## Alur pengumpulan data (collect.py)

1. **Bounding box** Jakarta `(-6.40, 106.65, -6.08, 107.00)` [S,W,N,E].
2. **Filter tag** kategori wisata (`tourism`, `leisure`, `historic`, `amenity`).
3. Query Overpass-QL **per kategori** (single-line; hindari 406 mod_security),
   ambil `node` (titik) + `way` (area, via centroid).
4. **fetch**: POST + `User-Agent`; retry backoff pada 429/504; fallback endpoint mirror.
5. **parse**: ekstrak koordinat, kategori, `opening_hours`, link.
6. **dedupe**: kunci `(nama, lat~4dp, lon~4dp)` buang overlap node/way.
7. Output `data/venues_raw.csv`.

## Engine rekomendasi

```
score = 0.30*similarity_konten + 0.35*kedekatan_geo
      + 0.20*popularitas + 0.15*buka_di_hari_terpilih
```

- **similarity_konten**: TF-IDF kategori + cosine similarity terhadap minat user.
- **kedekatan_geo**: haversine jarak turis→venue, dinormalisasi (dekat = tinggi).
- **popularitas**: `unique_visitors` ternormalisasi.
- **buka_di_hari**: 1 jika venue buka di hari terpilih, 0 jika tutup.

Bobot di `recommend.py` (`WEIGHTS`). **Cold-start friendly** — tak butuh riwayat user.
Param `only_open=True` → hanya tampilkan venue yang buka di hari terpilih.
Saat data rating user×venue tersedia, tambahkan collaborative filtering → hybrid penuh.

## Metode (untuk laporan riset)

- Jenis: *secondary data collection* + *purposive/criterion-based sampling*
  (kriteria = tag kategori wisata dalam batas geografis Jakarta).
- Teknik: spatial API query (Overpass), bukan web scraping.
- Limitasi: `unique_visitors` & `time_spent` sintetis; sebagian `opening_hours`
  pakai default kategori (`hours_source=default`).

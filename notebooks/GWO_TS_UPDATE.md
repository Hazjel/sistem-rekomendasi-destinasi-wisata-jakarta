# Update Optimizer: GA-PSO Hybrid -> GWO-TS

Ringkasan perubahan supaya website memakai model **GWO-TS** (Grey Wolf
Optimizer + Tabu Search), bukan lagi GA-PSO Hybrid.

## File yang ditambah / diubah (repo model)

- **BARU** `src/modeling/gwo_ts.py` — implementasi GWO-TS untuk TTDP
  (representasi permutasi, interface sama dgn `run_ga`/`run_pso`/`run_hybrid`:
  `run_gwo_ts(problem, ...) -> {best_perm, best_fitness, history}`).
- `config.py` — blok parameter `GWO_*` dan `TS_*` di bagian bawah.
- `src/api/itinerary_service.py` — daftarkan `gwo_ts` di `_ALGOS`; cabang
  `algorithm="auto"` sekarang me-resolve ke `gwo_ts` (dulu hybrid/ga).
- `src/api/api.py` — deskripsi field `algorithm` + docstring.
- `src/modeling/experiment.py` — tambah `GWO-TS` ke `ALGOS` untuk
  perbandingan di laporan.

Frontend (`web-wisata-jakarta`) **tidak perlu diubah**: frontend tidak pernah
mengirim `algorithm`, jadi otomatis ikut `auto` -> GWO-TS.

## Cara port dari notebook

Notebook GWO-TS memakai formulasi toy (per-zona, 4 tempat/hari, individu =
subset venue). Model yang dideploy memakai `TTDPProblem` berbasis **permutasi**
(himpunan kandidat tetap, yang dioptimasi hanya urutan; pembagian ke hari via
time-budget decoding di `problem.py`). Struktur algoritma dipertahankan persis:
leader alpha/beta/delta, jadwal `a = 2 - it*(2/n_iter)`, switch |A|<1
(eksploitasi: tarik ke delta 0.1 / beta 0.3 / alpha 0.6) vs |A|>=1 (eksplorasi),
refinement Tabu Search pada alpha tiap iterasi (tenure 10, 8 neighbor,
aspiration), elitisme wolf-0. Yang disesuaikan hanya operator: swap-sequence
murni + swap-mutation (bukan operator 'replace' zona), dan neighborhood TS
swap + insertion. Alasan lengkap ada di docstring `gwo_ts.py`.

## Menjalankan lokal

Data (`data/`) di-track Git LFS. Setelah clone:

```bash
git lfs pull    # ambil CSV dataset (clustered venues, time matrix, hotels)
python -m venv .venv && source .venv/bin/activate   # opsional
pip install -r requirements.txt

# smoke test optimizer:
python src/modeling/gwo_ts.py

# jalankan API (dari root repo):
uvicorn src.api.api:app --reload
# lalu jalankan frontend (repo web-wisata-jakarta): npm install && npm run dev
```

Yang dibutuhkan optimizer saat runtime hanya CSV di `data/processed/`
(clustered venues, `jakarta_travel_time_allpairs.csv`,
`jakarta_travel_time_inzone.csv`, `jakarta_hotels.csv`; motor opsional).
Folder cache JSON (`google_cache`, `wikipedia_cache`, `audit_cache`, dst) hanya
untuk pipeline preprocessing — tidak dipakai saat serving.

## Catatan tuning (jujur, perlu verifikasi)

Parameter default GWO-TS (`GWO_N_ITER=120`, pull 0.1/0.3/0.6, `TS_TENURE=10`,
`TS_MAX_NEIGHBORS=8`) mengikuti notebook, **belum** di-grid-search ulang pada
dataset final 161 venue seperti GA/PSO/Hybrid. Untuk klaim performa di laporan,
jalankan `python src/modeling/experiment.py` (membandingkan keempat algoritma
lintas skenario 1/3/5 hari) dan, bila perlu, tuning `GWO_*`/`TS_*` di
`config.py`. Pada uji sanity dataset kecil, GWO-TS berjalan benar (konvergen,
permutasi valid, reproducible) tapi belum tentu mengungguli Hybrid tanpa
tuning — verifikasi via eksperimen sebelum menyimpulkan.

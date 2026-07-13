# Panduan Deploy — Frontend (Vercel) + Backend (Render)

Sistem punya 2 bagian yang di-deploy terpisah:
- **Backend** FastAPI (repo ini) → **Render** (server Python persisten).
- **Frontend** React/Vite (repo `web-wisata-jakarta`) → **Vercel** (situs statis).

Backend harus online lebih dulu, karena frontend memanggilnya.

> **Catatan cold-start (Render free):** service tidur setelah ~15 menit idle.
> Request pertama sesudah tidur perlu ~30 detik untuk bangun. Sebelum demo/
> sidang, buka URL backend `…/health` sekali untuk "memanaskan" service.

---

## Bagian 1 — Backend ke Render

1. Push repo ini ke GitHub (sudah, kalau belum: `git push`).
2. Buka [render.com](https://render.com) → daftar (bisa via GitHub, gratis, tanpa kartu).
3. **New** → **Blueprint** → pilih repo ini. Render membaca `render.yaml` otomatis.
4. Setelah service dibuat, masuk **Environment**, isi:
   - `FRONTEND_ORIGINS` = URL Vercel kamu (isi setelah Bagian 2, mis.
     `https://web-wisata-jakarta.vercel.app`). Boleh beberapa, pisah koma.
   - `GOOGLE_PLACES_KEY` = (opsional) key Google Places untuk foto venue.
     Kosongkan kalau tak punya — sistem tetap jalan tanpa foto.
5. Tunggu build selesai. Catat URL backend, mis. `https://wisata-jakarta-api.onrender.com`.
6. Uji: buka `https://<backend>/health` → harus muncul `{"status":"ok", ...}`.

Kalau build gagal di `git lfs pull`: pastikan dataset CSV memang ada di repo
GitHub via LFS. Alternatif: commit 5 CSV serving (clustered venues, allpairs,
inzone, motor, hotels) sebagai file biasa di branch deploy.

---

## Bagian 2 — Frontend ke Vercel

1. Push repo `web-wisata-jakarta` ke GitHub.
2. Buka [vercel.com](https://vercel.com) → daftar via GitHub (gratis).
3. **Add New** → **Project** → import repo `web-wisata-jakarta`.
   Framework preset: **Vite** (otomatis terdeteksi).
4. **Environment Variables**, tambahkan:
   - `VITE_API_URL` = URL backend Render dari Bagian 1
     (mis. `https://wisata-jakarta-api.onrender.com`) — **tanpa** garis miring akhir.
5. **Deploy**. Catat URL frontend, mis. `https://web-wisata-jakarta.vercel.app`.

---

## Bagian 3 — Sambungkan (CORS)

1. Kembali ke Render → **Environment** → set `FRONTEND_ORIGINS` = URL Vercel
   (Bagian 2). Simpan → Render redeploy otomatis.
2. Buka URL Vercel. Rencanakan itinerary — kalau muncul rekomendasi, sambungan
   frontend↔backend berhasil.

Kalau muncul error CORS di console browser: pastikan `FRONTEND_ORIGINS` persis
sama dengan domain Vercel (termasuk `https://`, tanpa garis miring akhir).

---

## Ringkas alur data

```
Browser → Vercel (frontend statis) → fetch VITE_API_URL → Render (FastAPI)
                                                             ↓ load CSV sekali
                                                             ↓ CBF + GWO-TS
                                                          itinerary JSON
```

Peta & rute jalan (OSRM) diambil frontend langsung dari server publik OSRM —
tak lewat backend, tak butuh konfigurasi tambahan.

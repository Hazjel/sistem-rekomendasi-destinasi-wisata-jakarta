# Deploy Backend ke Hugging Face Spaces (gratis, persisten)

Backend FastAPI ini terlalu berat untuk serverless (scipy+pandas+sklearn ~240 MB
mendekati batas Vercel). Hugging Face Spaces (Docker SDK) menjalankannya sebagai
**server persisten gratis** tanpa batas ukuran ketat maupun batas waktu request.

## Langkah

1. Buat akun di [huggingface.co](https://huggingface.co) (gratis).
2. **New** → **Space**. Isi:
   - Owner/Name: mis. `namamu/wisata-jakarta-api`
   - SDK: **Docker** (bukan Gradio/Streamlit)
   - Visibility: Public (atau Private)
3. Space membuat repo git. Push isi repo model ini ke repo Space:
   ```bash
   git remote add space https://huggingface.co/spaces/<owner>/<name>
   git push space main
   ```
   (Space membaca `Dockerfile` di root otomatis.)
4. **Settings → Variables and secrets** di Space, tambah:
   - `FRONTEND_ORIGINS` = URL frontend Vercel (mis. `https://web-wisata.vercel.app`)
   - `GOOGLE_PLACES_KEY` = (opsional; foto sudah statis di frontend, jadi
     biasanya tak perlu)
5. Tunggu build (~5 menit pertama). URL backend:
   `https://<owner>-<name>.hf.space`
6. Uji: `https://<owner>-<name>.hf.space/health` → `{"status":"ok", ...}`.

## Sambungkan ke frontend

Di Vercel (frontend), set `VITE_API_URL` = URL Space di atas. Redeploy frontend.

## Catatan

- Space Docker persisten: tak "tidur" seagresif free tier lain; cold-start hanya
  saat build/restart, bukan tiap request.
- Port container = 7860 (default HF), sudah diset di `Dockerfile`.
- Data CSV serving sudah file biasa (bukan LFS) → langsung ikut ter-push.

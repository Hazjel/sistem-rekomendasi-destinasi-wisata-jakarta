# Backend FastAPI untuk Hugging Face Spaces (Docker SDK).
# HF Spaces menjalankan container ini; port 7860 = default HF.
FROM python:3.12-slim

# git + git-lfs untuk menarik dataset bila masih via LFS (5 CSV serving sudah
# file biasa, tapi ini aman bila ada file LFS lain yang dibutuhkan).
RUN apt-get update && apt-get install -y --no-install-recommends \
    git git-lfs && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps dulu (layer cache) — pakai requirements ramping serving.
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt uvicorn

# Salin sisa kode + data.
COPY . .

# HF Spaces mengharapkan app di port 7860.
EXPOSE 7860
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "7860"]

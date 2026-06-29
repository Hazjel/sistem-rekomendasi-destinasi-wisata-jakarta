"""Konfigurasi global proyek rekomendasi destinasi wisata Jakarta."""

# Bounding box Jakarta (south, west, north, east) -> fallback kalau area OSM gagal.
# CATATAN: bbox persegi overlap sebagian Bekasi/Depok/Tangerang. Filter utama
# pakai AREA_RELATION (boundary administratif asli) di build_query().
JAKARTA_BBOX = (-6.40, 106.65, -6.08, 107.00)

# Boundary administratif DKI Jakarta (admin_level=4) di Overpass, dicari via
# tag name+admin_level (bukan hardcode relation id -> lebih robust).
# https://www.openstreetmap.org/relation/6362934
JAKARTA_AREA_NAME = "Daerah Khusus Ibukota Jakarta"
JAKARTA_AREA_ADMIN_LEVEL = "4"

# Endpoint Overpass (OpenStreetMap). Gratis, tanpa API key.
# Coba urut; kalau satu sibuk/gagal pindah berikutnya.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OVERPASS_URL = OVERPASS_URLS[0]  # kompat lama

# Kategori OSM yang dianggap "destinasi wisata".
# key -> daftar value yang diterima (None = semua value pada key tsb).
TOURISM_FILTERS = {
    "tourism": ["attraction", "museum", "viewpoint", "zoo", "theme_park",
                "gallery", "artwork", "aquarium"],
    "leisure": ["park", "garden"],
    "historic": None,            # semua nilai historic (monument, memorial, dll)
    "amenity":  ["place_of_worship", "marketplace"],
}

# File output.
RAW_CSV = "data/venues_raw.csv"
ENRICHED_CSV = "data/venues_enriched.csv"

# Seed agar simulasi traffic reproducible.
RANDOM_SEED = 42

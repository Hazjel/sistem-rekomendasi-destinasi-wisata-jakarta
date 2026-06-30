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

# File output (OSM venue, pipeline 01_data_collection -> 02_preprocessing).
RAW_CSV = "data/raw/venues_osm_raw.csv"          # mentah dari Overpass (collect_osm.py, no dedupe)
CLEAN_CSV = "data/processed/venues_osm_clean.csv" # setelah dedupe + cluster-dedupe (clean_osm.py)
ENRICHED_CSV = "data/processed/venues_enriched.csv"

# Hotel (titik berangkat/pulang itinerary) -- dipisah dari venue wisata krn
# perannya beda: bukan diskor/direkomendasikan, cuma start/end point.
HOTEL_FILTERS = {
    "tourism": ["hotel", "guest_house", "hostel", "apartment"],
}
HOTEL_RAW_CSV = "data/raw/hotels_raw.csv"
HOTEL_ENRICHED_CSV = "data/processed/hotels_enriched.csv"

# Dataset Massive-STEPS-Jakarta (HuggingFace) -- check-in nyata, pelengkap
# trajectory/popularitas yang OSM tidak punya (lihat 01_data_collection/collect_steps.py).
STEPS_REPO_ID = "CRUISEResearchGroup/Massive-STEPS-Jakarta"
STEPS_CHECKINS_FILENAME = "jakarta_checkins.csv"
STEPS_CHECKINS_RAW_CSV = "data/raw/jakarta_checkins_raw.csv"         # mentah, output collect_steps.py
STEPS_CHECKINS_CLEAN_CSV = "data/processed/steps_checkins_clean.csv" # sesudah drop null, output clean_steps.py
STEPS_VENUES_RAW_CSV = "data/processed/steps_venues_raw.csv"         # agregasi per venue, output clean_steps.py
STEPS_FILTERED_CSV = "data/processed/steps_filtered.csv"

# Whitelist kategori wisata dari Massive-STEPS (Foursquare taxonomy).
# Kategori check-in di Foursquare dipilih BEBAS oleh user, bukan ground truth
# -> kategori generic (Plaza, Park, Garden, Zoo, Water Park, Scenic Lookout,
# Sculpture Garden, Art Gallery, Performing Arts Venue, Theater) terbukti
# berisi banyak noise (mall, kantor, lampu merah, smoking area, dst -- lihat
# spot-check di sesi data processing). Whitelist dipersempit ke kategori
# yang secara nama relatif spesifik/solid (museum, temple, beach bernama,
# monumen, situs sejarah, theme park).
STEPS_TOURISM_CATEGORIES = [
    "Aquarium", "Art Museum", "Beach", "Historic Site", "History Museum",
    "Monument / Landmark", "Museum", "Science Museum", "Temple",
    "Buddhist Temple", "Theme Park", "Theme Park Ride / Attraction",
    "Tourist Information Center", "Zoo",
]

# Keyword exclude di nama venue (lowercase substring match) -- kurasi tahap 2
# setelah whitelist kategori, buang sisa noise non-wisata yang masih lolos
# (cth "Museum Mandiri" itu nama gedung bank, bukan museum nyata; "Lampu
# merah pulo gadung" lolos kategori Scenic Lookout sebelum kategori itu di-drop).
STEPS_NAME_EXCLUDE_KEYWORDS = [
    "hotel", "apartemen", "apartment", "kantor", "office", "ruko", "puskesmas",
    "rumah sakit", "klinik", "lampu merah", "perempatan", "bunderan lalu lintas",
    "cuci mobil", "cuci motor", "parkir", "smoking area", "kost", "kos-kosan",
    "indomaret", "alfamart", "mandiri", "bank ", "bca", "bni", "btn",
    "swimming pool apartemen", "wisma ", "menara ", "gedung kantor",
]

# Merge Massive-STEPS (tulang punggung: POI nyata + popularitas check-in) +
# OSM (enrichment: jam buka, link referensi) by koordinat berdekatan.
MERGE_RADIUS_M = 150
MERGED_VENUES_CSV = "data/processed/merged_venues.csv"

# Clustering per zona (K-Means by lat/lon) -> input GA/PSO (next phase).
CLUSTER_K = 8
CLUSTERED_VENUES_CSV = "data/processed/clustered_venues.csv"

# Time matrix: waktu tempuh antar venue (beda dari time_spent = durasi di
# venue). OSRM public demo -- gratis, tanpa API key, tapi ToS-limited (bukan
# utk produksi/bulk besar) -> matrix dibatasi antar-venue dalam zone_id sama.
OSRM_BASE_URL = "http://router.project-osrm.org"
TIME_MATRIX_CSV = "data/processed/time_matrix.csv"
AVG_SPEED_KMH_FALLBACK = 20  # estimasi kondisi macet Jakarta, kalau OSRM gagal

# Seed agar simulasi traffic reproducible.
RANDOM_SEED = 42

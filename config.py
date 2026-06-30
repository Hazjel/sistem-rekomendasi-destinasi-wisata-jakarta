"""Konfigurasi global proyek rekomendasi destinasi wisata Jakarta."""

# Bounding box Jakarta (south, west, north, east) -> fallback kalau area OSM gagal.
# CATATAN: bbox persegi overlap sebagian Bekasi/Depok/Tangerang. Filter utama
# pakai AREA_RELATION (boundary administratif asli) di build_query().
JAKARTA_BBOX = (-6.37, 106.725, -6.08, 107.00)  # diperketat: selatan -6.37, barat 106.725

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

# Blacklist nama eksplisit -- venue yang lolos keyword-exclude tapi jelas bukan
# destinasi wisata (terdeteksi via spot-check manual).
STEPS_NAME_BLACKLIST = [
    # Batch 1: lolos filter awal, jelas bukan destinasi wisata
    "lobby",
    "ruang besar",
    "ivan's heart",
    "rawasari barat",
    "ccf ( kebudayaan perancis )",
    # Batch 2: spot-check manual per kategori + venue checkin_count rendah/bukan wisata
    # Monument / Landmark
    "percetakan negara republik indonesia",
    "gedung koni dki",
    "vice presidential palace",
    "gedung veteran ri",
    "adelwin landmark",
    "national trust for historic preservation",
    "veterans",
    # Art Museum
    "pertokoan globe pasar baru",
    # Historic Site
    "al-azhar",
    "makam wakaf sebrang",
    "jembatan bkt bambu duri",
    "traffic light taman suropati",
    "jl. raya tanjung barat selatan gg. 100",
    "pancoran.tugu",
    "1.5 x 1.5 thinking room",
    # Zoo
    "pasar ikan kartini",
    "p l a y g r o u n d",
    "pemancingan",
    "kandang rusa",
    "kandang macan taman safari indonesia",
    "salmon's new aquatic site",
    # Theme Park
    "amazone - itc permata hijau",
    "patung kuda laut",
    "jogging track rasuna",
    "kongkoow place of ilham's",
    "air mancur (depan indosat)",
    "al net",
    "rumah-ku",
    "emefer world",
    "pintu gerbang utama",
    "pintu masuk ancol",
    "tebettimurdalam",
    "the white [beach] party jakarta 2012",
    "astrazania - jelajahi dunia astra 2012",
    "dreamland",
    "fus1on 2012",
    "#fus1on2012",
    "#glowinpassfour",
    "iceberg xiv",
    "tasyaldy toys",
    "play house land",
    # Tourist Information Center (semua travel agent, bukan destinasi)
    "dwidaya tour",
    "gallery garuda indonesia",
    "mnc travel and services, highend building lt. 1",
    # checkin_count=1, nama informal bukan destinasi wisata proper
    "pik long beach",
    # Batch 5: audit menyeluruh per kategori — toko akuarium, kafe, pemancingan, duplikat wahana, noise
    # Aquarium: semua toko ikan hias / aquascape bukan destinasi wisata
    "cemani farm koi",
    "azis aquarium",
    "naratic aquarium design",
    "berkah rizki aquarium shop (rizki aquarium)",
    "rila design aquarium (rda led)",
    "putra aquarium",
    "dutamas aquarium toko",
    "fauzi aquarium meruya",
    "kanaya garden & aquatic",
    "rey aquarium",
    "sudut aquascape",
    "ikan hias laut - felix tropica",
    "sb aquarium",
    "toko mutiara aquarium",
    "java reef studio (pembuatan aquarium laut)",
    "pesona aquarium kebagusan",
    "under water theater",  # duplikat underwater theatre
    # Art Museum: bukan galeri/museum wisata
    "freedom ink tattoo jakarta",
    "mewatu coffee & gallery",
    "art cafe jakarta",
    # Theme Park: pemancingan, taman RT, rental PS, duplikat wahana
    "dna games rental playstation",
    "pemancingan \"caap\"",
    "pemancingan pondok agung (galatama lele)",
    "taman pemancingan ita",
    "rptra carina sayang",
    "rptra gedong trikora",
    "joglo under toll park",
    "teater terbuka unj",
    "wahana rajawali",
    "wahana rumah miring",
    "wahana turangga-tangga",
    "wahana kalila",
    "wahana tornado",
    "treasureland temple of fire dufan",
    "wahana treasure land",
    "simulator 3d, dufan",
    "funworld mall of indonesia",
    "fun world moi",
    "fun world moi (family recreation center)",
    "moiland theme park",
    "lollipop's playland & cafe",
    "lollipop gandaria city",
    "lollipop's living world",
    "kid fun world central park",
    "fun world central park",
    "fun world",
    "citra playland mall ciputra",
    "funworld treasure island",
    "histeria",
    "niagara-gara",
    # Historic Site: marketing gallery, spot foto dadakan, ulasan terlalu sedikit
    "pik 2 marketing gallery (marketing galeri/galeri pemasaran)",
    "spot hunting photo rumah kota tua",
    "pulomas historical site",
    # Museum: noise — warung, masjid, studio foto, batu keramat
    "warung buah segar.",
    "masjid nurul amanah",
    "loonami house k-pop studio",
    "batu tumbuh kramat jati",
    # Batch 4: spot-check dari Google Places tambahan — perusahaan, toko, makam, kolam renang
    "pt pembangunan jaya ancol tbk",
    "fantasi rekreasindo. pt tsm",
    "closed",
    "hic swimming pool",
    "hs agung swimming pool",
    "aquascaper",
    "huk aquatic",
    "dhika aquarium",
    "sarang sugar glider ii",
    "buku langka tmii",
    "situ cipondoh",
    "waduk haji dogol",
    "pgb (pulo gebang basuri)",
    "cagar buah condet",
    "masjid jami' at-taqwa brimob",
    "makam pangeran ayarif datuk banjir",
    "makom kramat guru abdurahman dan pangeran salim",
    # Batch 3: spot-check sesi 2026-06-30 — non-wisata, luar jakarta, ambigu
    # kantor pemerintah
    "bpkp dki jakarta i",
    # salon/kecantikan bukan destinasi wisata
    "lellidewi house of beauty & wellness",
    # gedung komersial
    "gedung cipta niaga",
    "gedung puspa pesona",
    "pt ciputra sentra. gedung mal ciputra jakarta lantai p1, jakarta.",
    "dci",
    # kolam renang/fasilitas hotel bukan destinasi mandiri
    "beach pool",
    "swimming pool",
    "kolam tenlis",
    # nama jalan/lokasi bukan destinasi
    "duren tiga",
    "jalan zamrud",
    "jbt pancoran - tegal parang",
    "muara baru",
    # tempat ibadah biasa (bukan destinasi wisata religi bersejarah)
    "gbi golden truly",
    "mesjid baiturrahman ancol",
    # venue di luar Jakarta
    "keraton solo",
    "lembang lake",
    "water sport tanjung benoa",
    "klenteng agung sam poo kong semarang",
    "prambanan temple",
    # rumah sakit
    "rsb alvernia agusta",
    # nama ambigu / tidak dikenal sebagai destinasi wisata jakarta
    "my black hawk",
    "observatory",
    "gelanggang remaja",
    "pantai bende",
    "markas batman",
    "deep blue sea",
    "coloseum",
    "sunday jazz festival",
    "faiz rayyan's private beach",
    "pos 8 port of tg. priok",
    "kedai acoy",
    "monkeymickey",
    "the bukit",
    "pantai mabak",
    "geography room",
    "greenbay's sea",
    "pgc \"penghuni terminal angker\"",
    "ody dive center - pramuka island",
    "negara api",
    "somewhere beach",
    "ruang bougenville",
    "yayasan dharma kasih sejahtera",
]

# Merge Massive-STEPS (tulang punggung: POI nyata + popularitas check-in) +
# OSM (enrichment: jam buka, link referensi) by koordinat berdekatan.
MERGE_RADIUS_M = 150
MERGED_VENUES_CSV = "data/processed/merged_venues.csv"
MERGED_VENUES_ENRICHED_CSV = "data/processed/merged_venues_enriched.csv"

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

"""
Merge venue hasil collect_steps_nontourism.py ke merged_venues_enriched.csv.
Filter otomatis berdasarkan kategori Foursquare + nama keyword.
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
os.chdir(r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
import pandas as pd
import config

CANDIDATES_CSV = "data/processed/steps_nontourism_candidates.csv"

# Kategori Foursquare yang auto-include (jelas wisata)
AUTO_INCLUDE_CATS = {
    'Park', 'Mosque', 'Theater', 'Performing Arts Venue', 'Sculpture Garden',
    'Garden', 'Lake', 'Water Park', 'Skating Rink', 'Art Gallery',
    'Concert Hall', 'Scenic Lookout', 'General Entertainment', 'Spiritual Center',
    'Movie Theater',  # Theater IMAX Keong Emas, dll -- difilter by nama di bawah
    'Playground',
}

# Kategori yang auto-exclude
AUTO_EXCLUDE_CATS = {
    'Nightclub', 'Track Stadium', 'Stadium', 'Volleyball Court',
    'Bike Rental / Bike Share', 'Light Rail Station', 'Farm',
}

# Nama yang auto-exclude (substring lowercase)
EXCLUDE_NAME_KW = [
    'jogging track', 'velodrome', 'velodome', 'gbi ', 'gky ', 'hkbp ', 'gki ',
    'gondola ancol', 'taman central park', 'tribeca park', 'tribeca nyc',
    # bioskop mall biasa (bukan destinasi wisata)
    'gandaria xxi', 'gading xxi', 'lotte shopping avenue xxi',
    'premiere kasablanka',
]

# Nama exact exclude (lowercase)
EXCLUDE_NAME_EXACT = {
    'pura aditya jaya',               # sudah ada di dataset
    'jogging track taman tebet barat', # sub-area
    'stadium jakarta',                 # nightclub
    'gor soemantri brodjonegoro',      # fasilitas olahraga
    'jakarta international velodrome', # fasilitas olahraga
    'velodrome jogging track',
    'stadion persija',                 # stadion bola, bukan destinasi wisata
    'lapangan volley basket candra naya school',
    'taman tanjung',                   # playground kecil
    'taman sungai sambas',             # playground kecil
}

# Gereja: hanya yang bersejarah/Katolik/ikonik (substring lowercase)
CHURCH_INCLUDE_KW = [
    'santa theresia', 'santa maria de fatima', 'gpib immanuel', 'gpib paulus',
    'gereja katedral', 'gereja santa', 'gereja katolik', 'gereja st.',
    'gereja st ', 'gereja santo', 'gereja kristus', 'gereja maria',
    'gereja st. petrus', 'gereja st. fr',
]

# Gereja denominasi biasa -- exclude
CHURCH_EXCLUDE_KW = [
    'gbi ', 'gky ', 'hkbp ', 'gki ', 'tiberias', 'gilgal', 'kemah tabernakel',
    'paroki salib suci', 'mawar sharon',
]

def should_include(row):
    name = row['name']
    name_lower = name.lower().strip()
    cat = row['venue_category']
    rating = row['google_rating_count']

    if name_lower in EXCLUDE_NAME_EXACT:
        return False, f'exact exclude'

    if any(kw in name_lower for kw in EXCLUDE_NAME_KW):
        return False, f'name keyword exclude'

    if cat in AUTO_EXCLUDE_CATS:
        return False, f'kategori {cat}'

    if cat == 'Church':
        if any(kw in name_lower for kw in CHURCH_EXCLUDE_KW):
            return False, 'gereja denominasi biasa'
        if any(kw in name_lower for kw in CHURCH_INCLUDE_KW):
            return True, 'gereja bersejarah/Katolik'
        return False, 'gereja tidak dikenal sebagai destinasi wisata'

    if cat == 'Movie Theater':
        # Hanya IMAX/theater yang bukan bioskop mall biasa
        if 'imax' in name_lower or 'keong' in name_lower:
            return True, 'theater IMAX ikonik'
        return False, 'bioskop mall biasa'

    if cat == 'Playground':
        if rating >= 2000:
            return True, 'playground populer'
        return False, 'playground kecil'

    if cat in AUTO_INCLUDE_CATS:
        return True, f'kategori {cat}'

    return True, 'default include'


def main():
    candidates = pd.read_csv(CANDIDATES_CSV)
    existing = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV,
                           dtype={'sublocality': 'object', 'locality': 'object',
                                  'primary_type': 'object', 'business_status': 'object',
                                  'photo_ref': 'object', 'description': 'object'})

    exist_names = set(existing['name'].str.lower().str.strip())

    included = []
    excluded = []
    skipped_dup = []

    for _, row in candidates.iterrows():
        name_lower = row['name'].lower().strip()
        if name_lower in exist_names:
            skipped_dup.append(row['name'])
            continue
        ok, reason = should_include(row)
        if ok:
            included.append((row, reason))
        else:
            excluded.append((row['name'], row['venue_category'], int(row['google_rating_count']), reason))

    print(f"Kandidat: {len(candidates)}")
    print(f"Skip duplikat (sudah di dataset): {len(skipped_dup)}")
    print(f"Include: {len(included)}")
    print(f"Exclude: {len(excluded)}")

    if skipped_dup:
        print(f"\nDuplikat dilewati: {skipped_dup}")

    print(f"\n=== VENUE YANG AKAN DITAMBAH ({len(included)}) ===")
    for row, reason in sorted(included, key=lambda x: -x[0]['google_rating_count']):
        print(f"  {int(row['google_rating_count']):>7} | {row['venue_category']:<30} | {row['name']}")

    print(f"\n=== DIBUANG ({len(excluded)}) ===")
    for name, cat, rating, reason in sorted(excluded, key=lambda x: -x[2]):
        print(f"  {rating:>7} | {cat:<30} | {name} [{reason}]")

    if not included:
        print("\nTidak ada venue baru.")
        return

    # Build rows untuk merge
    DAYS_ID = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
    day_cols = [f'{d}_buka' for d in DAYS_ID] + [f'{d}_tutup' for d in DAYS_ID]

    new_rows = []
    # Cari max venue_id numerik dari existing untuk assign baru
    existing_google = existing[existing['venue_id'].astype(str).str.startswith('google_')]
    max_gid = 0
    for vid in existing_google['venue_id']:
        try:
            n = int(str(vid).replace('google_', ''))
            max_gid = max(max_gid, n)
        except:
            pass

    for i, (row, reason) in enumerate(included):
        new_id = f"google_{max_gid + i + 1:05d}"
        new_row = {col: None for col in existing.columns}
        new_row['venue_id'] = new_id
        new_row['name'] = row['name']
        new_row['venue_category'] = row['venue_category']
        new_row['latitude'] = row['latitude']
        new_row['longitude'] = row['longitude']
        new_row['checkin_count'] = row['checkin_count']
        new_row['google_rating_count'] = row['google_rating_count']
        new_row['description'] = row.get('description', '')
        new_row['hours_source'] = 'default_category'
        for d in DAYS_ID:
            new_row[f'{d}_buka'] = 'Tutup'
            new_row[f'{d}_tutup'] = 'Tutup'
        new_rows.append(new_row)

    new_df = pd.DataFrame(new_rows)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
    print(f"\nTersimpan -> {config.MERGED_VENUES_ENRICHED_CSV}")
    print(f"Total venue: {len(existing)} + {len(new_rows)} = {len(combined)}")


if __name__ == '__main__':
    main()

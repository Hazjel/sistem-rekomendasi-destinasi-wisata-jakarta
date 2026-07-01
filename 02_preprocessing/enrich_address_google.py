"""
Backfill kolom yang masih kosong di merged_venues_enriched.csv via Google Places API.

Kolom yang diisi:
  - address (formattedAddress)
  - description (jika kosong)
  - google_types, primary_type (jika kosong)
  - google_rating, google_rating_count (jika kosong)
  - business_status (jika kosong)
  - good_for_children, wheelchair_accessible, has_parking, accepts_cashless, has_restroom (jika kosong)
  - photo_ref (jika kosong)
  - sublocality, locality (jika kosong)

Cache: data/processed/google_cache_v2/ — menyimpan seluruh Place Details per venue_id.
Cache lama (google_cache/) tidak di-overwrite.

Input:  data/processed/merged_venues_enriched.csv
Output: data/processed/merged_venues_enriched.csv (in-place)
        data/processed/clustered_venues.csv (in-place, jika kolom zone_id ada)
"""
import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd
import requests
import config

KEY = os.environ.get('GOOGLE_PLACES_KEY', '')
BASE = 'https://places.googleapis.com/v1'
CACHE_DIR = 'data/processed/google_cache_v2'
DAYS_ID = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
GDAY = {0: 'Minggu', 1: 'Senin', 2: 'Selasa', 3: 'Rabu', 4: 'Kamis', 5: 'Jumat', 6: 'Sabtu'}

FIELD_MASK = ','.join([
    'formattedAddress',
    'regularOpeningHours',
    'rating',
    'userRatingCount',
    'priceLevel',
    'editorialSummary',
    'types',
    'primaryType',
    'websiteUri',
    'goodForChildren',
    'nationalPhoneNumber',
    'businessStatus',
    'accessibilityOptions',
    'parkingOptions',
    'paymentOptions',
    'restroom',
    'photos',
    'addressComponents',
    'location',
])


def search_place_id(name, lat, lon):
    url = f'{BASE}/places:searchText'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': KEY,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress',
    }
    body = {
        'textQuery': f'{name} Jakarta',
        'locationBias': {'circle': {'center': {'latitude': lat, 'longitude': lon}, 'radius': 500.0}},
        'maxResultCount': 1,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        places = r.json().get('places', [])
        return places[0]['id'] if places else None
    except Exception:
        return None


def get_place_details(place_id):
    url = f'{BASE}/places/{place_id}'
    headers = {'X-Goog-Api-Key': KEY, 'X-Goog-FieldMask': FIELD_MASK}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def parse_details(data):
    if not data:
        return None

    # Address components
    sublocality, locality = None, None
    for comp in data.get('addressComponents', []):
        types = comp.get('types', [])
        if 'administrative_area_level_4' in types:
            sublocality = comp.get('longText')
        elif 'administrative_area_level_2' in types:
            locality = comp.get('longText')

    # Parking, payment, accessibility
    acc = data.get('accessibilityOptions', {})
    parking = data.get('parkingOptions', {})
    payment = data.get('paymentOptions', {})

    photos = data.get('photos', [])

    return {
        'address': data.get('formattedAddress'),
        'rating': data.get('rating'),
        'user_rating_count': data.get('userRatingCount'),
        'price_level': data.get('priceLevel'),
        'description': data.get('editorialSummary', {}).get('text'),
        'types': ','.join(data.get('types', [])),
        'primary_type': data.get('primaryType'),
        'website': data.get('websiteUri'),
        'business_status': data.get('businessStatus'),
        'good_for_children': data.get('goodForChildren'),
        'wheelchair_accessible': acc.get('wheelchairAccessibleEntrance'),
        'has_parking': any(parking.values()) if parking else None,
        'accepts_cashless': payment.get('acceptsCreditCards') or payment.get('acceptsDebitCards'),
        'has_restroom': data.get('restroom'),
        'photo_ref': photos[0].get('name') if photos else None,
        'sublocality': sublocality,
        'locality': locality,
    }


def fill_row(df, idx, parsed):
    """Isi kolom yang KOSONG saja — tidak overwrite yang sudah ada."""
    def _fill(col, val):
        if val is not None and (pd.isna(df.at[idx, col]) if col in df.columns else True):
            df.at[idx, col] = val

    _fill('address', parsed.get('address'))
    _fill('description', parsed.get('description'))
    _fill('google_types', parsed.get('types'))
    _fill('primary_type', parsed.get('primary_type'))
    _fill('google_rating', parsed.get('rating'))
    _fill('google_rating_count', parsed.get('user_rating_count'))
    _fill('business_status', parsed.get('business_status'))
    _fill('good_for_children', parsed.get('good_for_children'))
    _fill('wheelchair_accessible', parsed.get('wheelchair_accessible'))
    _fill('has_parking', parsed.get('has_parking'))
    _fill('accepts_cashless', parsed.get('accepts_cashless'))
    _fill('has_restroom', parsed.get('has_restroom'))
    _fill('photo_ref', parsed.get('photo_ref'))
    _fill('sublocality', parsed.get('sublocality'))
    _fill('locality', parsed.get('locality'))
    if parsed.get('website') and 'References' in df.columns and pd.isna(df.at[idx, 'References']):
        df.at[idx, 'References'] = parsed['website']


def needs_fill(df, idx):
    """Return True kalau venue masih punya kolom penting yang kosong."""
    check_cols = ['address', 'description', 'google_types', 'primary_type',
                  'google_rating', 'business_status']
    for col in check_cols:
        if col in df.columns and pd.isna(df.at[idx, col]):
            return True
    return False


def main():
    if not KEY:
        raise RuntimeError('Set env var GOOGLE_PLACES_KEY terlebih dahulu.')

    os.makedirs(CACHE_DIR, exist_ok=True)

    targets = [config.MERGED_VENUES_ENRICHED_CSV]
    if os.path.exists(config.CLUSTERED_VENUES_CSV):
        targets.append(config.CLUSTERED_VENUES_CSV)

    for csv_path in targets:
        df = pd.read_csv(csv_path, dtype={'sublocality': 'object', 'locality': 'object',
                                          'primary_type': 'object', 'business_status': 'object',
                                          'photo_ref': 'object', 'description': 'object',
                                          'address': 'object', 'References': 'object',
                                          'osm_url': 'object', 'google_types': 'object',
                                          'last_checkin': 'object'})

        # Tambah kolom address jika belum ada
        if 'address' not in df.columns:
            df['address'] = None

        n_filled, n_cached, n_skip, n_fail = 0, 0, 0, 0

        for i, (idx, row) in enumerate(df.iterrows()):
            if not needs_fill(df, idx):
                n_skip += 1
                continue

            vid = str(row['venue_id']).replace('/', '_')
            cache_path = os.path.join(CACHE_DIR, vid + '.json')

            if os.path.exists(cache_path):
                raw = json.load(open(cache_path, encoding='utf-8'))
                n_cached += 1
            else:
                place_id = search_place_id(row['name'], row['latitude'], row['longitude'])
                time.sleep(0.3)
                raw = get_place_details(place_id) if place_id else None
                time.sleep(0.3)
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(raw, f, ensure_ascii=False)

            parsed = parse_details(raw)
            if parsed:
                fill_row(df, idx, parsed)
                n_filled += 1
            else:
                n_fail += 1

            if (i + 1) % 25 == 0:
                df.to_csv(csv_path, index=False)
                print(f'  {i+1}/{len(df)} | filled:{n_filled} cached:{n_cached} skip:{n_skip} fail:{n_fail}')

        df.to_csv(csv_path, index=False)
        print(f'\n=== {csv_path} ===')
        print(f'Total venue: {len(df)}')
        print(f'Filled: {n_filled}, Cached: {n_cached}, Skip (sudah lengkap): {n_skip}, Fail: {n_fail}')

        miss = df.isnull().sum()
        miss = miss[miss > 0].sort_values(ascending=False)
        print('\nMissing setelah enrich:')
        for col, n in miss.items():
            print(f'  {col:<35} {n:>4} ({n/len(df)*100:.0f}%)')


if __name__ == '__main__':
    main()

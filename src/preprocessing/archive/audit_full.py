"""
Audit lengkap semua venue di clustered_venues.csv:
1. Reverse geocode: apakah koordinat benar-benar di Jakarta?
2. Nama mismatch: Google return nama venue berbeda jauh?
3. businessStatus: CLOSED?
4. Duplikat koordinat (radius 50m, nama berbeda)
5. Jam masih default_category
Output: data/processed/audit_full_report.csv
"""
import os, sys, json, time, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
os.chdir(r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
import pandas as pd
import numpy as np
import config
from importlib import import_module
dki_mod = import_module('02_preprocessing.dki_boundary')
dki_poly = dki_mod.load_dki_polygon()

KEY = os.environ.get('GOOGLE_PLACES_KEY', '')
BASE = 'https://places.googleapis.com/v1'
CACHE_DIR = 'data/processed/google_cache'
AUDIT_CACHE = 'data/processed/audit_cache'
os.makedirs(AUDIT_CACHE, exist_ok=True)

df = pd.read_csv('data/processed/clustered_venues.csv')
DAYS_ID = ['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu']
buka_cols = [f'{d}_buka' for d in DAYS_ID]

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

def name_similarity(a, b):
    """Hitung overlap kata antara dua nama (case-insensitive)"""
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0
    return len(a_words & b_words) / max(len(a_words), len(b_words))

def lookup_place(name, lat, lon, venue_id):
    cp = os.path.join(AUDIT_CACHE, f'{venue_id}.json')
    if os.path.exists(cp):
        return json.load(open(cp, encoding='utf-8'))
    r = requests.post(BASE + '/places:searchText', headers={
        'Content-Type': 'application/json', 'X-Goog-Api-Key': KEY,
        'X-Goog-FieldMask': 'places.displayName,places.location,places.businessStatus,places.userRatingCount,places.addressComponents'
    }, json={
        'textQuery': name + ' Jakarta',
        'locationBias': {'circle': {'center': {'latitude': lat, 'longitude': lon}, 'radius': 500}},
        'maxResultCount': 1
    }, timeout=15)
    time.sleep(0.2)
    places = r.json().get('places', [])
    if not places:
        json.dump(None, open(cp, 'w'))
        return None
    p = places[0]
    data = {
        'g_name': p['displayName']['text'],
        'g_lat': p['location']['latitude'],
        'g_lon': p['location']['longitude'],
        'status': p.get('businessStatus', ''),
        'rating_count': p.get('userRatingCount', 0),
        'kota': next((c['longText'] for c in p.get('addressComponents',[])
                      if 'administrative_area_level_2' in c.get('types',[])), ''),
    }
    json.dump(data, open(cp, 'w', encoding='utf-8'), ensure_ascii=False)
    return data

# === AUDIT DUPLIKAT KOORDINAT ===
print("=== CEK DUPLIKAT KOORDINAT (radius 50m) ===")
lats = df['latitude'].values
lons = df['longitude'].values
dup_pairs = []
for i in range(len(df)):
    for j in range(i+1, len(df)):
        d = haversine_m(lats[i], lons[i], lats[j], lons[j])
        if d < 50:
            dup_pairs.append((df.iloc[i]['name'], df.iloc[j]['name'], round(d,1)))
if dup_pairs:
    for a, b, d in dup_pairs:
        print(f"  {d}m | {a} <-> {b}")
else:
    print("  Tidak ada duplikat koordinat.")

# === AUDIT JAM DEFAULT ===
mask_default = df['hours_source'] == 'default_category'
print(f"\n=== JAM MASIH DEFAULT_CATEGORY: {mask_default.sum()} ===")
for _, r in df[mask_default].iterrows():
    print(f"  [{r['venue_category']:<25}] {r['name']}")

# === AUDIT KOORDINAT PER VENUE (Google reverse geocode) ===
print(f"\n=== AUDIT KOORDINAT + STATUS per venue ({len(df)} total) ===")
issues = []

for i, row in df.iterrows():
    vid = str(row['venue_id'])
    name = row['name']
    lat, lon = row['latitude'], row['longitude']

    # Cek dalam polygon DKI
    in_dki = dki_mod.is_in_dki(lat, lon, dki_poly)
    if not in_dki:
        issues.append({'venue_id': vid, 'name': name, 'issue': 'LUAR_DKI',
                       'detail': f'lat={lat:.4f} lon={lon:.4f}'})
        print(f"  [LUAR_DKI] {name} ({lat:.4f}, {lon:.4f})")
        continue

    # Google lookup
    data = lookup_place(name, lat, lon, vid)
    if data is None:
        issues.append({'venue_id': vid, 'name': name, 'issue': 'NOT_FOUND_GOOGLE', 'detail': ''})
        print(f"  [NOT_FOUND] {name}")
        continue

    g_name = data['g_name']
    g_lat, g_lon = data['g_lat'], data['g_lon']
    status = data['status']
    kota = data['kota']
    dist = haversine_m(lat, lon, g_lat, g_lon)
    sim = name_similarity(name, g_name)

    # Flag issues
    if status in ('CLOSED_PERMANENTLY', 'CLOSED_TEMPORARILY'):
        issues.append({'venue_id': vid, 'name': name, 'issue': status,
                       'detail': f'Google: {g_name}'})
        print(f"  [{status}] {name} -> {g_name}")
    elif dist > 500:
        issues.append({'venue_id': vid, 'name': name, 'issue': 'COORD_MISMATCH',
                       'detail': f'{dist:.0f}m jauh | Google: {g_name} ({g_lat:.4f},{g_lon:.4f})'})
        print(f"  [COORD_MISMATCH {dist:.0f}m] {name} -> {g_name}")
    elif sim < 0.2 and dist > 200:
        issues.append({'venue_id': vid, 'name': name, 'issue': 'NAME_MISMATCH',
                       'detail': f'sim={sim:.2f} dist={dist:.0f}m | Google: {g_name}'})
        print(f"  [NAME_MISMATCH] {name} -> {g_name} (sim={sim:.2f})")
    elif kota and 'jakarta' not in kota.lower() and 'kepulauan' not in kota.lower():
        issues.append({'venue_id': vid, 'name': name, 'issue': 'LUAR_JAKARTA_KOTA',
                       'detail': f'kota={kota} | Google: {g_name}'})
        print(f"  [LUAR_JAKARTA] {name} -> kota: {kota}")
    else:
        print(f"  [OK] {name}")

print(f"\n=== SUMMARY ===")
print(f"Total venue: {len(df)}")
print(f"Issues ditemukan: {len(issues)}")
if issues:
    iss_df = pd.DataFrame(issues)
    print(iss_df.groupby('issue').size().to_string())
    iss_df.to_csv('data/processed/audit_full_report.csv', index=False)
    print(f"\nReport -> data/processed/audit_full_report.csv")

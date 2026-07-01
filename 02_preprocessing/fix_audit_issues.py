"""
Fix hasil audit:
1. Hapus venue luar Jakarta
2. Hapus venue COORD_MISMATCH parah (koordinat salah total)
3. Hapus duplikat (koordinat hampir sama, venue sama)
4. Fix koordinat yang salah tapi venue masih valid
5. Re-enrich jam buka untuk yang masih default_category
"""
import os, sys, json, time, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
os.chdir(r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
import pandas as pd
import numpy as np
import config

KEY = os.environ.get('GOOGLE_PLACES_KEY', '')
BASE = 'https://places.googleapis.com/v1'
DAYS_ID = ['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu']

# === HAPUS: luar Jakarta ===
REMOVE_LUAR_JAKARTA = {
    'transera waterpark',
    'rainbow garden',
    'wahana bermain rainbow adventure park pondok gede',
    'tugu tarian langit - kota harapan indah',
    'istana boneka jatiwaringin (isbon)',
    'istana boneka harapan indah (isbon)',
}

# === HAPUS: koordinat salah total (bukan venue wisata Jakarta) ===
REMOVE_COORD_WRONG = {
    'palm bay water park',
    'watersplash citra 2 hero',
    'emporium fish jakarta - toko ikan hias dan predator',
    'akvodecor - pakar aquascape dan aquarium air laut',
    'yerushalayim bible artefacts museum',
    'acrylic production & wedding card acrylic (produksi akrilik & kartu undangan akrilik)',
    'underwater theatre',   # 976km off, venue berbeda
}

# === HAPUS: duplikat (simpan yang lebih deskriptif/lebih tinggi checkin) ===
REMOVE_DUPLICATES = {
    'kidzania jakarta',                    # duplikat KidZania
    'vihara dharma jaya toasebio',         # duplikat Vihara Dharma Jaya Toasebio (huruf kapital)
    'fine art and ceramic museum',         # duplikat Museum Seni Rupa dan Keramik
    'komunitas salihara arts center',      # duplikat Komunitas Salihara
    # Wahana DUFAN sub-venue (0.0m dari DUFAN induk) -- hapus wahana individual
    'wahana hysteria',
    'wahana tornado',
    'wahana arung jeram (river raft ride)',
    'halilintar',                          # juga coord wrong 16km
    'wahana kincir raksasa bianglala (giant wheel)',
    'wahana kicir-kicir (power surge)',
    'niagara-gara',
    # Sub-venue DUFAN lain
    'treasure land (dufan)',
    'treasureland temple of fire dufan',
    'wahana treasure land',
    'histeria',
    # Sub-venue Museum
    'gedung gajah',                        # sub-area Museum Nasional
    'ruang etnografi museum fatahilah',    # sub-area Museum Fatahillah
    # Duplikat pantai Ancol
    'ancol bay city, north jakarta',       # sub-area Pantai Indah Ancol
    # Sub-venue Ragunan
    'arena satwa gajah',
    'arena satwa harimau sumatera',
    'orang utan a. ragunan zoo',
    # Duplikat koordinat lain
    'museum indonesia',                    # 15km mismatch, beda dengan Museum Nasional
    'patung mohammad husni thamrin',       # duplikat Bundaran HI area
    # Sub-venue Gelanggang Samudera
    'dolphin show gelanggang samudra',     # duplikat Ocean Dream Samudra
    'taman lumba-lumba',                   # sub-venue Ocean Dream Samudra
    '4d ocean dream samudra ancol',        # sub-venue
    'pentas singa laut dan burung',        # sub-venue
    # Sub-venue Fun World
    'fun world moi (family recreation center)', # duplikat Fun World MOI
    'kid fun world central park',          # duplikat Fun World Central Park
    # Sub-venue Ancol
    'monumen ancol',                       # kecil, non-destinasi
    'marina batavia',                      # duplikat area Marina
    # Sub-venue TMII
    'anjungan tmii',                       # generic, bukan spesifik
    'stasiun kereta api mini',             # transportasi internal TMII
    'skylift indonesia',                   # transportasi internal TMII
    'monumen persahabatan.tmii',           # monumen kecil dalam TMII
    # Venue meragukan
    'spot hunting photo rumah kota tua',   # bukan venue wisata formal
    'puri marina club house',              # private club
    'jakarta beach city',                  # area komersial
    'taman komplek',                       # terlalu generic
    'ancol beach',                         # duplikat pantai ancol area
    'sunda kelapa - batavia',              # duplikat Batavia/Sunda Kelapa
    'gedung joeang',                       # duplikat Museum Gedung Joang '45
    'sasmita loka ahmad yani museum',      # duplikat Museum Sasmitaloka Achmad Yani
    'museum mh. thamrin',                  # duplikat Museum M. Husni Thamrin
    'keprajuritan musium tmii',            # duplikat Museum Keprajuritan
    'fresh water world tmii',              # duplikat Dunia Air Tawar
}

# === FIX KOORDINAT: update ke koordinat Google yang benar ===
FIX_COORDS = {
    # nama_lower: (lat_baru, lon_baru)
    'bundaran bank indonesia (bundaran patung kuda)': (-6.1866, 106.8228),  # Bundaran BI Jl. MH Thamrin (bukan Monas)
    'masjid at tarbiyah': (-6.2857, 106.8066),  # Masjid At-Tarbiyah Cipete (bukan Cilandak)
    'dermaga one - ancol': (-6.1235, 106.8327),  # Dermaga Ancol yang benar
    'lubang buaya': (-6.2851, 106.9082),          # Monumen Lubang Buaya
    'trick art japanese 3d painting exhibition': (-6.2088, 106.8213), # lokasi asli di Sudirman
    'danau sunter': (-6.1547, 106.8761),           # Danau Sunter lokasi benar
    'taman impian jaya ancol (ancol dreamland)': (-6.1254, 106.8372), # entrance Ancol
    'pantai marina ancol': (-6.1200, 106.8450),    # Marina Ancol
    'pantai segara ancol': (-6.1185, 106.8405),    # Pantai Segara
    'pasir putih': (-6.1190, 106.8395),            # Pasir Putih Ancol
    'lampion theme\'s park, taman mini indonesia indah': (-6.3025, 106.8950), # dalam TMII
    'rumah adat minangkabau': (-6.3024, 106.8939), # Anjungan Sumatera Barat TMII
    'galeria sophilia': (-6.2650, 106.7890),       # koordinat Galeria Sophilia asli
    'vihara toasebio': (-6.1465, 106.8168),        # Vihara Toasebio Glodok
    'pantai carnaval': (-6.1220, 106.8360),        # Pantai Carnaval Ancol
    'ancol beach': (-6.1200, 106.8400),            # Ancol Beach
}


def get_google_hours(name, lat, lon, venue_id):
    cache_dir = 'data/processed/audit_cache'
    cp = os.path.join(cache_dir, f'hours_{venue_id}.json')
    if os.path.exists(cp):
        return json.load(open(cp, encoding='utf-8'))
    r = requests.post(BASE + '/places:searchText', headers={
        'Content-Type': 'application/json', 'X-Goog-Api-Key': KEY,
        'X-Goog-FieldMask': 'places.regularOpeningHours,places.displayName,places.location,places.businessStatus'
    }, json={
        'textQuery': name + ' Jakarta',
        'locationBias': {'circle': {'center': {'latitude': lat, 'longitude': lon}, 'radius': 300}},
        'maxResultCount': 1
    }, timeout=15)
    time.sleep(0.2)
    places = r.json().get('places', [])
    if not places:
        json.dump(None, open(cp, 'w'))
        return None
    p = places[0]
    data = {'hours': p.get('regularOpeningHours', {}), 'name': p['displayName']['text']}
    json.dump(data, open(cp, 'w', encoding='utf-8'), ensure_ascii=False)
    return data


def parse_periods(periods):
    """Parse Google periods -> dict {hari: (buka, tutup)}"""
    DAY_MAP = {0:'Minggu',1:'Senin',2:'Selasa',3:'Rabu',4:'Kamis',5:'Jumat',6:'Sabtu'}
    if not periods:
        return {}
    is_24h = len(periods) > 0 and all('close' not in p for p in periods)
    if is_24h:
        return {d: ('00:00','23:59') for d in DAYS_ID}
    result = {}
    for p in periods:
        o = p.get('open', {})
        c = p.get('close', {})
        day_idx = o.get('day')
        if day_idx is None:
            continue
        day_name = DAY_MAP.get(day_idx)
        if not day_name:
            continue
        oh = str(o.get('hour',0)).zfill(2)
        om = str(o.get('minute',0)).zfill(2)
        ch = str(c.get('hour',0)).zfill(2)
        cm = str(c.get('minute',0)).zfill(2)
        result[day_name] = (f'{oh}:{om}', f'{ch}:{cm}')
    return result


def main():
    df = pd.read_csv('data/processed/clustered_venues.csv',
                     dtype={'sublocality':'object','locality':'object',
                            'primary_type':'object','business_status':'object',
                            'photo_ref':'object','description':'object'})
    print(f"Awal: {len(df)} venue")

    # 1. Hapus luar Jakarta
    mask_luar = df['name'].str.lower().str.strip().isin(REMOVE_LUAR_JAKARTA)
    print(f"\nHapus luar Jakarta: {mask_luar.sum()}")
    for n in df[mask_luar]['name']:
        print(f"  - {n}")
    df = df[~mask_luar].copy()

    # 2. Hapus coord wrong
    mask_coord = df['name'].str.lower().str.strip().isin(REMOVE_COORD_WRONG)
    print(f"\nHapus coord salah total: {mask_coord.sum()}")
    for n in df[mask_coord]['name']:
        print(f"  - {n}")
    df = df[~mask_coord].copy()

    # 3. Hapus duplikat
    mask_dup = df['name'].str.lower().str.strip().isin(REMOVE_DUPLICATES)
    print(f"\nHapus duplikat/sub-venue: {mask_dup.sum()}")
    for n in df[mask_dup]['name']:
        print(f"  - {n}")
    df = df[~mask_dup].copy()

    # 4. Fix koordinat
    print(f"\nFix koordinat {len(FIX_COORDS)} venue:")
    for name_lower, (lat_new, lon_new) in FIX_COORDS.items():
        mask = df['name'].str.lower().str.strip() == name_lower
        if mask.sum() > 0:
            df.loc[mask, 'latitude'] = lat_new
            df.loc[mask, 'longitude'] = lon_new
            print(f"  Fix: {df.loc[mask,'name'].values[0]} -> ({lat_new}, {lon_new})")

    print(f"\nSetelah cleanup: {len(df)} venue")

    # 5. Re-enrich jam default_category
    mask_default = df['hours_source'] == 'default_category'
    targets = df[mask_default].copy()
    print(f"\nRe-enrich jam: {len(targets)} venue masih default_category")

    enriched = 0
    for idx, row in targets.iterrows():
        vid = str(row['venue_id'])
        name = row['name']
        lat, lon = row['latitude'], row['longitude']
        data = get_google_hours(name, lat, lon, vid)
        if not data:
            print(f"  [NOT FOUND] {name}")
            continue
        periods = data.get('hours', {}).get('periods', [])
        if not periods:
            print(f"  [NO HOURS] {name} (Google: {data.get('name','')})")
            continue
        parsed = parse_periods(periods)
        if not parsed:
            print(f"  [PARSE FAIL] {name}")
            continue
        for day, (buka, tutup) in parsed.items():
            df.loc[idx, f'{day}_buka'] = buka
            df.loc[idx, f'{day}_tutup'] = tutup
        # isi hari yang tidak ada di parsed -> Tutup
        for day in DAYS_ID:
            if day not in parsed:
                df.loc[idx, f'{day}_buka'] = 'Tutup'
                df.loc[idx, f'{day}_tutup'] = 'Tutup'
        df.loc[idx, 'hours_source'] = 'google_places'
        enriched += 1
        print(f"  [OK] {name} -> {data.get('name','')} | {len(parsed)} hari")

    print(f"\nEnrich jam: {enriched}/{len(targets)} berhasil")
    still_default = (df['hours_source'] == 'default_category').sum()
    print(f"Masih default_category: {still_default}")

    # Save ke enriched (bukan clustered -- biar bisa re-cluster)
    df.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
    print(f"\nTersimpan -> {config.MERGED_VENUES_ENRICHED_CSV}")
    print(f"Total akhir: {len(df)} venue")


if __name__ == '__main__':
    main()

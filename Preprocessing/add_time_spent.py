"""
Tambah kolom time_spent_minutes ke clustered_venues.csv dan merged_venues_enriched.csv.

Metode: category-based baseline + popularity scaling (google_rating_count).
Formula: scale = 1 + 0.3 * log10(rating_count / base_threshold)
         time_spent = base_minutes * clamp(scale, 0.7, 1.8)

Referensi metodologi:
- Lim et al. (2019) "Tour Recommendation and Trip Planning using Location-based Social Media: A Survey"
- Gavalas et al. (2014) "A survey on algorithmic approaches for solving tourist trip design problems"
"""
import sys, os, math
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
os.chdir(r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
import pandas as pd
import config

# Base durasi (menit) per kategori + threshold rating_count
# Base = estimasi kunjungan rata-rata venue "normal" kategori itu
# Threshold = rating_count yang dianggap "ukuran normal" kategori itu
CATEGORY_CONFIG = {
    # (base_minutes, threshold_rating_count)
    # Theme Park & hiburan besar
    'Theme Park':                    (240, 50000),
    'Water Park':                    (180, 10000),
    'Amusement Park':                (240, 50000),
    'General Entertainment':         (180, 50000),
    # Zoo & alam
    'Zoo':                           (150, 20000),
    'Aquarium':                      (90,  10000),
    'Nature / Park':                 (90,  10000),
    'Park':                          (60,  5000),
    'Garden':                        (60,  3000),
    'Beach':                         (90,  5000),
    'Lake':                          (45,  2000),
    'Sculpture Garden':              (30,  2000),
    'Scenic Lookout':                (30,  2000),
    # Museum & budaya
    'Museum':                        (90,  5000),
    'History Museum':                (90,  5000),
    'Art Museum':                    (75,  3000),
    'Art Gallery':                   (60,  2000),
    'Science Museum':                (90,  5000),
    'Historic Site':                 (60,  3000),
    'Monument / Landmark':           (30,  5000),
    # Tempat ibadah
    'Mosque':                        (45,  5000),
    'Church':                        (45,  3000),
    'Temple':                        (45,  2000),
    'Spiritual Center':              (45,  2000),
    # Theater & pertunjukan
    'Theater':                       (120, 2000),
    'Performing Arts Venue':         (120, 2000),
    'Concert Hall':                  (120, 2000),
    'Movie Theater':                 (120, 1000),
    # Rekreasi
    'Skating Rink':                  (90,  3000),
    'Playground':                    (60,  5000),
    'Pool':                          (120, 3000),
    'Kolam Renang':                  (120, 3000),
    # Default
    'DEFAULT':                       (60,  3000),
}

def compute_time_spent(category, rating_count):
    cfg = CATEGORY_CONFIG.get(category, CATEGORY_CONFIG['DEFAULT'])
    base, threshold = cfg
    if rating_count and rating_count > 0:
        scale = 1 + 0.3 * math.log10(max(rating_count, 1) / threshold)
        scale = max(0.7, min(1.8, scale))
    else:
        scale = 1.0
    return round(base * scale)

def main():
    for csv_path in [config.MERGED_VENUES_ENRICHED_CSV, config.CLUSTERED_VENUES_CSV]:
        df = pd.read_csv(csv_path, dtype={'sublocality':'object','locality':'object',
                                          'primary_type':'object','business_status':'object',
                                          'photo_ref':'object','description':'object'})
        df['google_rating_count'] = pd.to_numeric(df['google_rating_count'], errors='coerce').fillna(0)

        df['time_spent_minutes'] = df.apply(
            lambda r: compute_time_spent(r['venue_category'], r['google_rating_count']), axis=1
        )

        df.to_csv(csv_path, index=False)
        print(f"\nTersimpan -> {csv_path}")

        # Summary per kategori
        print(f"{'Kategori':<30} {'Count':>5} {'Min':>5} {'Median':>7} {'Max':>5}")
        print("-" * 55)
        for cat, grp in df.groupby('venue_category')['time_spent_minutes']:
            print(f"  {cat:<28} {len(grp):>5} {int(grp.min()):>5} {int(grp.median()):>7} {int(grp.max()):>5}")

        print(f"\nTotal: {len(df)} venue")
        print(f"Range time_spent: {df['time_spent_minutes'].min()} - {df['time_spent_minutes'].max()} menit")
        print(f"Median: {df['time_spent_minutes'].median():.0f} menit")

        # Spot check venue besar
        print(f"\nSpot check venue besar:")
        besar = ['Monumen Nasional (MONAS)', 'Dunia Fantasi (DUFAN)',
                 'Ragunan Zoo', 'Taman Mini Indonesia Indah (TMII)',
                 'Museum Nasional Indonesia', 'Masjid Istiqlal']
        for name in besar:
            row = df[df['name'].str.lower() == name.lower()]
            if not row.empty:
                r = row.iloc[0]
                print(f"  {r['name']}: {r['time_spent_minutes']} menit "
                      f"(cat={r['venue_category']}, rating_count={int(r['google_rating_count'])})")

if __name__ == '__main__':
    main()

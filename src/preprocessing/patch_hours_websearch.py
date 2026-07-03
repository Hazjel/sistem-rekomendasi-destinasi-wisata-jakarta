"""
Patch jam buka via hasil web search untuk venue yang Google Places API
tidak mengembalikan data jam akurat.

Kasus:
- Outdoor/taman 24 jam: Danau Sunter, Taman Lawang, Taman Langsat, Bundaran
- Theater TIM (Graha Bhakti Budaya, Teater Jakarta): 09:00-21:00 walk-in
- Masjid Al-Bina: 05:00-22:00 (jadwal sholat umum)
- Gereja-gereja bersejarah Katolik: jam misa dari website resmi

Sumber: website resmi masing-masing venue (diverifikasi manual saat data collection).
Venue ini mendapat hours_source='web_search'.

Input:  data/processed/merged_venues_enriched.csv
Output: data/processed/merged_venues_enriched.csv (in-place)
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import pandas as pd
import config

DAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']


def set_hours(df, name_lower, hours_per_day):
    """
    hours_per_day: dict hari -> (buka, tutup), atau tuple single untuk semua hari,
                   atau None untuk Tutup.
    """
    idx = df[df['name'].str.lower().str.strip() == name_lower].index
    if len(idx) == 0:
        print(f"  SKIP (tidak ditemukan): {name_lower}")
        return
    for i in idx:
        if isinstance(hours_per_day, tuple):
            buka, tutup = hours_per_day
            for d in DAYS:
                df.at[i, f'{d}_buka'] = buka
                df.at[i, f'{d}_tutup'] = tutup
        elif isinstance(hours_per_day, dict):
            for d in DAYS:
                val = hours_per_day.get(d)
                if val is None:
                    df.at[i, f'{d}_buka'] = 'Tutup'
                    df.at[i, f'{d}_tutup'] = 'Tutup'
                else:
                    df.at[i, f'{d}_buka'] = val[0]
                    df.at[i, f'{d}_tutup'] = val[1]
        df.at[i, 'hours_source'] = 'web_search'
    print(f"  Patch: {name_lower}")


def main():
    df = pd.read_csv(config.MERGED_VENUES_ENRICHED_CSV)
    print(f"Total venue: {len(df)}")

    # Outdoor / taman / bundaran: buka 24 jam
    outdoor_24h = [
        'danau sunter',
        'bunderan air mancur monas',
        'bundaran bank indonesia (bundaran patung kuda)',
        'taman lawang',
        'taman langsat',
    ]
    for name in outdoor_24h:
        set_hours(df, name, ('00:00', '23:59'))

    # Theater TIM: walk-in 09:00-21:00 semua hari
    set_hours(df, 'graha bhakti budaya', ('09:00', '21:00'))
    set_hours(df, 'teater jakarta (teater besar)', ('09:00', '21:00'))

    # Masjid Al-Bina: 05:00-22:00
    set_hours(df, 'masjid al-bina', ('05:00', '22:00'))

    # Gereja Santa Maria de Fatima Toasebio: jam misa (Senin-Jumat 06:00-07:00, Sabtu 18:00-19:30, Minggu 07:30-19:30)
    set_hours(df, 'gereja santa maria de fatima toasebio', {
        'Senin':   ('06:00', '07:00'),
        'Selasa':  ('06:00', '07:00'),
        'Rabu':    ('06:00', '07:00'),
        'Kamis':   ('06:00', '07:00'),
        'Jumat':   ('06:00', '07:00'),
        'Sabtu':   ('18:00', '19:30'),
        'Minggu':  ('07:30', '19:30'),
    })

    # Gereja Santo Yoseph: Senin-Jumat 05:45-07:00, Sabtu 17:00-18:30, Minggu 06:30-19:30
    set_hours(df, 'gereja santo yoseph', {
        'Senin':   ('05:45', '07:00'),
        'Selasa':  ('05:45', '07:00'),
        'Rabu':    ('05:45', '07:00'),
        'Kamis':   ('05:45', '07:00'),
        'Jumat':   ('05:45', '07:00'),
        'Sabtu':   ('17:00', '18:30'),
        'Minggu':  ('06:30', '19:30'),
    })

    # Gereja Katolik Salib Suci: Senin-Jumat 05:30-06:30, Sabtu 18:00-19:30, Minggu 07:00-19:30
    set_hours(df, 'gereja katolik salib suci', {
        'Senin':   ('05:30', '06:30'),
        'Selasa':  ('05:30', '06:30'),
        'Rabu':    ('05:30', '06:30'),
        'Kamis':   ('05:30', '06:30'),
        'Jumat':   ('05:30', '06:30'),
        'Sabtu':   ('18:00', '19:30'),
        'Minggu':  ('07:00', '19:30'),
    })

    df.to_csv(config.MERGED_VENUES_ENRICHED_CSV, index=False)
    print(f"\nTersimpan -> {config.MERGED_VENUES_ENRICHED_CSV}")
    print(f"Venue web_search: {(df['hours_source'] == 'web_search').sum()}")


if __name__ == '__main__':
    main()

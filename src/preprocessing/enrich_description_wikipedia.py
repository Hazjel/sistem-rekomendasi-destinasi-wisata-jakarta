"""
Enrich kolom description via Wikipedia API (Indonesia + English fallback).
Hanya untuk venue yang description masih kosong.

Strategi per venue:
1. Direct lookup: Wikipedia ID dengan nama venue
2. Search API: cari judul artikel paling relevan
3. Fallback: Wikipedia EN
4. Kalau semua gagal: biarkan kosong

Sumber: Wikipedia REST API (CC BY-SA, bebas riset, tanpa API key)
Cache: data/processed/wikipedia_cache/ (json per venue_id)

Input:  data/processed/merged_venues_enriched.csv
Output: data/processed/merged_venues_enriched.csv (in-place)
        data/processed/jakarta_tourism_venues_clustered.csv (in-place)
"""
import json, os, sys, time, unicodedata, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import pandas as pd
import requests
import config

CACHE_DIR = 'data/processed/wikipedia_cache'
HEADERS = {'User-Agent': 'WisataJakartaResearch/1.0 (academic research; contact: humic-research)'}
TIMEOUT = 10


def slugify(text):
    """Nama venue -> Wikipedia title candidate."""
    text = text.strip()
    # Ganti karakter khusus umum
    text = re.sub(r'\s*\(.*?\)', '', text)  # hapus parenthesis
    text = text.strip()
    return text


def wiki_summary_direct(title, lang='id'):
    """GET /page/summary/{title} — Wikipedia REST API."""
    encoded = requests.utils.quote(title.replace(' ', '_'))
    url = f'https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            extract = data.get('extract', '').strip()
            # Tolak kalau artikel disambiguasi atau terlalu pendek
            if len(extract) > 50 and 'may refer to' not in extract and 'dapat merujuk' not in extract:
                return extract
    except Exception:
        pass
    return None


def wiki_search(query, lang='id'):
    """Search API -> ambil judul pertama -> direct lookup."""
    url = f'https://{lang}.wikipedia.org/w/api.php'
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': query,
        'srlimit': 3,
        'format': 'json',
    }
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=TIMEOUT)
        results = r.json().get('query', {}).get('search', [])
        for result in results:
            title = result['title']
            # Filter hasil yang jelas tidak relevan
            title_lower = title.lower()
            query_lower = query.lower()
            # Minimal ada 1 kata utama yang match
            query_words = set(query_lower.split()) - {'the', 'di', 'dan', 'atau', 'of', 'in'}
            if not any(w in title_lower for w in query_words if len(w) > 3):
                continue
            extract = wiki_summary_direct(title, lang)
            if extract:
                return extract
    except Exception:
        pass
    return None


def get_wikipedia_description(name, venue_id, venue_category, lat, lon):
    """Coba semua strategi, return (description, source) atau (None, None)."""
    cache_path = os.path.join(CACHE_DIR, f'{str(venue_id).replace("/", "_")}.json')

    if os.path.exists(cache_path):
        cached = json.load(open(cache_path, encoding='utf-8'))
        return cached.get('description'), cached.get('source')

    slug = slugify(name)
    result = None
    source = None

    # 1. Direct ID Wikipedia
    result = wiki_summary_direct(slug, 'id')
    if result:
        source = 'wikipedia_id_direct'

    # 2. Search ID Wikipedia
    if not result:
        time.sleep(0.2)
        result = wiki_search(f'{slug} Jakarta', 'id')
        if result:
            source = 'wikipedia_id_search'

    # 3. Direct EN Wikipedia
    if not result:
        time.sleep(0.2)
        result = wiki_summary_direct(slug, 'en')
        if result:
            source = 'wikipedia_en_direct'

    # 4. Search EN Wikipedia
    if not result:
        time.sleep(0.2)
        result = wiki_search(f'{slug} Jakarta', 'en')
        if result:
            source = 'wikipedia_en_search'

    # Simpan cache
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump({'description': result, 'source': source}, f, ensure_ascii=False)

    return result, source


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)

    targets = [config.MERGED_VENUES_ENRICHED_CSV]
    if os.path.exists(config.CLUSTERED_VENUES_CSV):
        targets.append(config.CLUSTERED_VENUES_CSV)

    for csv_path in targets:
        df = pd.read_csv(csv_path, dtype={'description': 'object', 'sublocality': 'object',
                                          'locality': 'object', 'primary_type': 'object',
                                          'business_status': 'object'})

        if 'description_source' not in df.columns:
            df['description_source'] = None

        missing_desc = df[df['description'].isna()].index.tolist()
        print(f'\n{csv_path}')
        print(f'Venue description kosong: {len(missing_desc)}')

        n_filled, n_cached, n_fail = 0, 0, 0

        for i, idx in enumerate(missing_desc):
            row = df.loc[idx]
            vid = str(row['venue_id'])
            cache_path = os.path.join(CACHE_DIR, f'{vid.replace("/", "_")}.json')
            from_cache = os.path.exists(cache_path)

            desc, source = get_wikipedia_description(
                row['name'], vid, row.get('venue_category'), row['latitude'], row['longitude']
            )
            time.sleep(0.3)

            if desc:
                df.at[idx, 'description'] = desc
                df.at[idx, 'description_source'] = source
                if from_cache:
                    n_cached += 1
                else:
                    n_filled += 1
                print(f'  [{source}] {row["name"][:50]}: {desc[:60]}...')
            else:
                n_fail += 1

            if (i + 1) % 20 == 0:
                df.to_csv(csv_path, index=False)
                print(f'  -- progress {i+1}/{len(missing_desc)}: filled={n_filled} cached={n_cached} fail={n_fail}')

        df.to_csv(csv_path, index=False)

        total_filled = n_filled + n_cached
        print(f'\nSelesai: {total_filled}/{len(missing_desc)} venue dapat description dari Wikipedia')
        print(f'  Baru query: {n_filled}, Dari cache: {n_cached}, Tidak ditemukan: {n_fail}')
        print(f'Description kosong setelah enrich: {df["description"].isna().sum()}')

        if 'description_source' in df.columns:
            print('\ndescription_source breakdown:')
            print(df['description_source'].value_counts(dropna=False).to_string())


if __name__ == '__main__':
    main()

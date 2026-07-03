"""
Lookup Google Places untuk venue STEPS di luar kategori tourism.
Filter: checkin >= 10, lalu cek google_rating_count >= 500.
Exclude Google types yang jelas bukan wisata (restoran, toko, kantor, dll).
Cache per venue_id di data/processed/google_cache/steps_{venue_id}.json
Output: data/processed/steps_nontourism_candidates.csv
"""
import os, sys, json, time, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
os.chdir(r'd:\humic\sistem rekomendasi destinasi wisata jakarta')
import pandas as pd
import config

KEY = os.environ.get("GOOGLE_PLACES_KEY", "")
if not KEY:
    sys.exit("Set env var GOOGLE_PLACES_KEY")

BASE = "https://places.googleapis.com/v1"
CACHE_DIR = "data/processed/google_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

MIN_CHECKIN = 10        # pre-filter sebelum Google lookup
MIN_RATING_COUNT = 500  # threshold "venue publik dikenal luas"

# Kategori Foursquare yang jelas bukan wisata -- skip tanpa perlu Google lookup
FOURSQUARE_EXCLUDE_CATS = {
    "Shopping Mall", "Office", "Building", "University", "Indonesian Restaurant",
    "Coffee Shop", "Café", "Restaurant", "Convenience Store", "Food Court",
    "Road", "Food Truck", "High School", "Asian Restaurant", "Ramen Restaurant",
    "Chinese Restaurant", "College Classroom", "Train Station", "Grocery Store",
    "Hotel", "Fast Food Restaurant", "Japanese Restaurant",
    "Residential Building (Apartment / Condo)", "Sushi Restaurant",
    "Seafood Restaurant", "Hospital", "Bookstore", "Bus Line", "Bakery",
    "Department Store", "Bank", "Pizza Place", "Fried Chicken Joint",
    "Gym / Fitness Center", "Burger Joint", "Dessert Shop", "Tea Room",
    "Salon / Barbershop", "Donut Shop", "Karaoke Bar", "School",
    "General College & University", "Government Building", "Automotive Shop",
    "Coworking Space", "Clothing Store", "Electronics Store", "Gas Station",
    "Bus Station", "College Academic Building", "Ice Cream Shop",
    "College Cafeteria", "Snack Place", "Soup Place", "Italian Restaurant",
    "Parking", "Boutique", "American Restaurant", "Housing Development",
    "Hardware Store", "Breakfast Spot", "Spa", "BBQ Joint", "Diner",
    "Pool", "College Library", "Tech Startup", "Flea Market",
    "Farmers Market", "Drugstore", "French Restaurant", "Shoe Store",
    "College Auditorium", "Dim Sum Restaurant", "Korean Restaurant",
    "Bar", "Paper / Office Supplies Store", "Malay Restaurant",
    "Bike Shop", "Women's Store", "Furniture / Home Store",
    "Vegetarian / Vegan Restaurant", "Post Office", "Food & Drink Shop",
    "Assisted Living", "Medical School", "Police Station",
    "Thai Restaurant", "Auditorium", "Funeral Home", "Toy / Game Store",
    "College Residence Hall", "Gourmet Shop", "Bowling Alley",
    "Elementary School", "Fish & Chips Shop", "Arts & Crafts Store",
    "Pet Store", "Accessories Store", "Dumpling Restaurant",
    "Auto Dealership", "Internet Cafe", "Gaming Cafe", "Trade School",
    "Hotel Bar", "Boarding House", "Swiss Restaurant", "Travel Agency",
    "Cocktail Bar", "College Math Building", "College & University",
    "Fraternity House", "Resort", "City Hall", "African Restaurant",
    "Deli / Bodega", "Smoke Shop", "Law School", "German Restaurant",
    "Sports Bar", "Mexican Restaurant", "Candy Store", "Turkish Restaurant",
    "Wings Joint", "Vietnamese Restaurant", "Thrift / Vintage Store",
    "Motorcycle Shop", "Rental Car Location", "Fire Station",
    "New American Restaurant", "Middle School", "Capitol Building",
    "Music Venue", "Lounge", "Rock Club", "Beer Garden",
    "Steakhouse", "Multiplex", "Student Center", "Cosmetics Shop",
    "Wine Bar", "Pool Hall", "Bridge", "General Travel", "Gym",
    "Community College", "Medical Center", "Neighborhood",
    "Basketball Court", "Soccer Field", "Soccer Stadium",
    "Event Space", "Convention Center", "Harbor / Marina",
    "Miscellaneous Shop", "Other Great Outdoors",
}

# Google types spesifik wisata -- HARUS ada minimal 1 agar lolos
# tourist_attraction TIDAK dipakai -- Google kasih label ini ke mall, RS, kampus
TOURISM_GOOGLE_TYPES = {
    "museum", "art_gallery", "amusement_park", "zoo", "aquarium",
    "stadium", "park", "natural_feature", "campground",
    "place_of_worship", "hindu_temple", "mosque", "church",
    "performing_arts_theater", "movie_theater", "bowling_alley",
    "rv_park", "tourist_attraction",  # tourist_attraction tetap tapi sebagai secondary
}

def cache_path(venue_id):
    return os.path.join(CACHE_DIR, f"steps_{venue_id}.json")

def lookup_google(name, lat, lon):
    r = requests.post(BASE + "/places:searchText", headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": KEY,
        "X-Goog-FieldMask": "places.displayName,places.location,places.userRatingCount,places.businessStatus,places.types,places.editorialSummary"
    }, json={
        "textQuery": name + " Jakarta",
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": 300}},
        "maxResultCount": 1
    }, timeout=15)
    if r.status_code != 200:
        return None
    places = r.json().get("places", [])
    return places[0] if places else None

def main():
    df = pd.read_csv("data/processed/steps_venues_raw.csv")
    df["checkin_count"] = pd.to_numeric(df["checkin_count"], errors="coerce").fillna(0)

    in_tourism = df["venue_category"].isin(config.STEPS_TOURISM_CATEGORIES)
    in_whitelist = df["name"].str.lower().isin({w.lower() for w in config.STEPS_TOURISM_WHITELIST})
    outside = df[~in_tourism & ~in_whitelist].copy()

    # Pre-filter 1: buang kategori Foursquare yang jelas bukan wisata (hemat API call)
    outside = outside[~outside["venue_category"].isin(FOURSQUARE_EXCLUDE_CATS)].copy()

    # Pre-filter 2: checkin minimum
    candidates = outside[outside["checkin_count"] >= MIN_CHECKIN].copy()
    candidates = candidates.sort_values("checkin_count", ascending=False).reset_index(drop=True)

    print(f"Venue STEPS di luar kategori tourism: {len(df[~in_tourism & ~in_whitelist])}")
    print(f"Setelah buang kategori noise Foursquare: {len(outside)}")
    print(f"Setelah filter checkin >= {MIN_CHECKIN}: {len(candidates)}")
    print(f"Akan di-lookup Google Places...\n")

    results = []
    ok = skip_cache = miss = below_threshold = excluded_type = 0

    for i, row in candidates.iterrows():
        vid = str(row["venue_id"])
        name = row["name"]
        lat, lon = row["latitude"], row["longitude"]
        cp = cache_path(vid)

        if os.path.exists(cp):
            data = json.load(open(cp, encoding="utf-8"))
            skip_cache += 1
        else:
            place = lookup_google(name, lat, lon)
            time.sleep(0.2)
            if place is None:
                miss += 1
                print(f"  [{i+1}/{len(candidates)}] NOT_FOUND: {name}")
                json.dump(None, open(cp, "w"))
                continue
            data = {
                "g_name": place["displayName"]["text"],
                "rating_count": place.get("userRatingCount", 0),
                "status": place.get("businessStatus", ""),
                "types": place.get("types", []),
                "desc": place.get("editorialSummary", {}).get("text", ""),
                "lat": place["location"]["latitude"],
                "lon": place["location"]["longitude"],
            }
            json.dump(data, open(cp, "w", encoding="utf-8"), ensure_ascii=False)

        if data is None:
            miss += 1
            continue

        types_set = set(data.get("types", []))
        rating_count = data.get("rating_count", 0)
        status = data.get("status", "")

        if status in ("CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"):
            below_threshold += 1
            continue

        if rating_count < MIN_RATING_COUNT:
            below_threshold += 1
            continue

        # Harus ada minimal 1 Google type wisata spesifik
        # tourist_attraction boleh lolos HANYA kalau Foursquare kategori-nya
        # tidak jelas komersial (sudah difilter di atas, tapi double-check)
        has_specific_tourism = bool(types_set & (TOURISM_GOOGLE_TYPES - {"tourist_attraction"}))
        has_tourist_attr = "tourist_attraction" in types_set
        # tourist_attraction saja tidak cukup (mall, RS juga dapat ini)
        # tapi kalau ada bersama types wisata lain -> ok
        if not has_specific_tourism and not has_tourist_attr:
            excluded_type += 1
            continue
        # Kalau HANYA tourist_attraction tanpa types wisata spesifik -> reject
        if not has_specific_tourism and has_tourist_attr:
            # Cek apakah ada indikasi venue komersial di types
            commercial = {"shopping_mall", "store", "restaurant", "food",
                         "cafe", "lodging", "hospital", "school", "university",
                         "bank", "gas_station", "transit_station"}
            if types_set & commercial:
                excluded_type += 1
                continue

        ok += 1
        results.append({
            "venue_id": vid,
            "name": name,
            "venue_category": row["venue_category"],
            "latitude": lat,
            "longitude": lon,
            "checkin_count": row["checkin_count"],
            "g_name": data["g_name"],
            "google_rating_count": rating_count,
            "google_types": ",".join(data["types"]),
            "description": data["desc"],
        })
        print(f"  [OK] {name} | {rating_count} ulasan | {row['venue_category']}")

    print(f"\nSelesai: ok={ok} cache={skip_cache} miss={miss} below_threshold={below_threshold} excluded_type={excluded_type}")

    if results:
        out = pd.DataFrame(results)
        out.to_csv("data/processed/steps_nontourism_candidates.csv", index=False)
        print(f"Tersimpan -> data/processed/steps_nontourism_candidates.csv ({len(results)} venue)")
        print("\nDistribusi kategori:")
        print(out["venue_category"].value_counts().to_string())
    else:
        print("Tidak ada kandidat baru.")

if __name__ == "__main__":
    main()

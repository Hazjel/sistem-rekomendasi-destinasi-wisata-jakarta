"""
Helper: polygon batas administratif DKI Jakarta.
Dipakai clean_merged.py dan merge_google_venues.py untuk filter koordinat.

Polygon dibuat dari koordinat batas administratif DKI Jakarta (approximate,
cukup akurat untuk membedakan DKI vs Tangerang/Depok/Bekasi).

Kepulauan Seribu ditangani terpisah dengan bbox laut utara Jakarta.
"""
from shapely.geometry import Point, MultiPolygon, Polygon
from shapely.ops import unary_union

# Polygon daratan DKI Jakarta (approximate, clockwise dari barat-laut)
# Sumber: batas administratif DKI Jakarta, diverifikasi manual vs Google Maps
_DKI_DARATAN = [
    # Barat Laut (Penjaringan/Pluit/PIK/Kapuk/Kamal Muara)
    # PIK koordinat: lon=106.735, lat=-6.089 → polygon harus cover ini
    (106.7100, -6.0800),  # Kamal Muara barat laut (titik paling barat DKI utara)
    (106.7300, -6.0850),  # Kalideres/Cengkareng utara
    (106.7450, -6.0900),  # Kapuk utara
    (106.7550, -6.0950),
    (106.7800, -6.0850),
    # Utara (Pantai Utara, Marunda)
    (106.8200, -6.0800),
    (106.8700, -6.0900),
    (106.9200, -6.0850),
    (106.9700, -6.0850),  # Marunda/Cilincing utara
    # Timur (Cilincing/Koja/Marunda)
    (106.9900, -6.1000),
    (106.9900, -6.1300),
    (106.9850, -6.1600),
    # Timur Bekasi border
    (106.9800, -6.1900),
    (106.9750, -6.2100),
    (106.9600, -6.2400),
    (106.9400, -6.2600),
    # Tenggara (Cipayung/Ciracas, batas Bekasi)
    (106.9300, -6.2900),
    (106.9100, -6.3100),
    (106.8850, -6.3200),
    # Selatan (Jagakarsa/Pasar Minggu, batas Depok)
    (106.8600, -6.3350),
    (106.8350, -6.3400),
    (106.8100, -6.3350),
    # Barat Daya (Pesanggrahan/Kebayoran Lama, batas Tangsel)
    # Bintaro (Tangsel) ada di lon~106.754 lat~-6.269 — harus di LUAR polygon
    # Batas DKI-Tangsel di sini sekitar lon 106.770-106.780
    (106.7850, -6.3200),
    (106.7750, -6.3050),
    (106.7700, -6.2800),
    (106.7700, -6.2500),  # Kebayoran Lama / Ciputat border
    # Barat (Cengkareng/Kalideres, batas Tangerang)
    (106.7550, -6.2300),
    (106.7400, -6.2100),
    (106.7250, -6.1900),
    (106.7150, -6.1500),
    (106.7100, -6.1200),
    # Barat Laut kembali ke titik awal
    (106.7100, -6.0800),
]

# Kepulauan Seribu: bbox laut utara Jakarta
_KEPULAUAN_SERIBU_BBOX = (106.40, -6.00, 106.85, -4.99)


def load_dki_polygon():
    """Return shapely geometry yang cover DKI Jakarta (daratan + Kepulauan Seribu)."""
    daratan = Polygon(_DKI_DARATAN)
    kepseribu = Polygon([
        (_KEPULAUAN_SERIBU_BBOX[0], _KEPULAUAN_SERIBU_BBOX[1]),
        (_KEPULAUAN_SERIBU_BBOX[2], _KEPULAUAN_SERIBU_BBOX[1]),
        (_KEPULAUAN_SERIBU_BBOX[2], _KEPULAUAN_SERIBU_BBOX[3]),
        (_KEPULAUAN_SERIBU_BBOX[0], _KEPULAUAN_SERIBU_BBOX[3]),
    ])
    return unary_union([daratan, kepseribu])


def is_in_dki(lat, lon, dki_polygon):
    """Return True jika koordinat (lat, lon) berada dalam polygon DKI Jakarta."""
    return dki_polygon.contains(Point(lon, lat))

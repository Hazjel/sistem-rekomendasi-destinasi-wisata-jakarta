"""
Parser tag OSM `opening_hours` -> jam buka/tutup per hari.

OSM opening_hours grammar lengkap sangat kompleks; di sini ditangani
kasus umum yang menutup mayoritas data:
    "24/7"
    "Mo-Su 09:00-21:00"
    "Mo-Fr 08:00-17:00; Sa 09:00-13:00; Su off"
    "Mo,We,Fr 10:00-18:00"
    "Tu-Su 09:00-16:00; Mo off"

Output: dict {hari_indo: (buka, tutup) | None}
    None = tutup hari itu.
Kasus tak terparse -> kembalikan None semua (biar fallback enrich jalan).
"""
import re

# Urutan hari OSM -> nama Indonesia.
OSM_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
OSM_IDX = {d: i for i, d in enumerate(OSM_DAYS)}

TIME_RE = re.compile(r"([0-2]?\d:[0-5]\d)\s*-\s*([0-2]?\d:[0-5]\d)")


def _expand_days(spec):
    """'Mo-Fr' / 'Mo,We' / 'Sa' -> list index hari 0..6."""
    idxs = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            ia, ib = OSM_IDX.get(a.strip()), OSM_IDX.get(b.strip())
            if ia is None or ib is None:
                continue
            if ia <= ib:
                idxs.extend(range(ia, ib + 1))
            else:  # wrap, mis. Sa-Mo
                idxs.extend(list(range(ia, 7)) + list(range(0, ib + 1)))
        else:
            i = OSM_IDX.get(part)
            if i is not None:
                idxs.append(i)
    return idxs


def parse_opening_hours(raw):
    """Parse string opening_hours -> {hari_indo: (buka,tutup)|None}."""
    result = {d: None for d in DAYS_ID}
    if not raw or not isinstance(raw, str):
        return result
    raw = raw.strip()

    if raw == "24/7":
        for d in DAYS_ID:
            result[d] = ("00:00", "24:00")
        return result

    matched_any = False
    for rule in raw.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        time_m = TIME_RE.search(rule)
        is_off = re.search(r"\b(off|closed)\b", rule, re.I)
        # bagian hari = teks sebelum jam/off.
        day_part = rule
        if time_m:
            day_part = rule[:time_m.start()].strip()
        elif is_off:
            day_part = rule[:is_off.start()].strip()

        # tanpa spesifikasi hari -> berlaku semua hari (mis. "09:00-17:00").
        if not day_part or not re.search(r"Mo|Tu|We|Th|Fr|Sa|Su", day_part):
            day_idxs = list(range(7))
        else:
            day_idxs = _expand_days(day_part)

        for i in day_idxs:
            if is_off and not time_m:
                result[DAYS_ID[i]] = None
                matched_any = True
            elif time_m:
                result[DAYS_ID[i]] = (time_m.group(1), time_m.group(2))
                matched_any = True

    if not matched_any:
        return {d: None for d in DAYS_ID}
    return result


if __name__ == "__main__":
    samples = [
        "24/7",
        "Mo-Su 09:00-21:00",
        "Mo-Fr 08:00-17:00; Sa 09:00-13:00; Su off",
        "Mo,We,Fr 10:00-18:00",
        "Tu-Su 09:00-16:00; Mo off",
        "",
    ]
    for s in samples:
        print(repr(s), "->", parse_opening_hours(s))

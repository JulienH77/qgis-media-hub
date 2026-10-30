# -*- coding: utf-8 -*-
"""Radio station catalogue and safe persistence helpers, no QGIS dependency.

Radio Browser click counts are directory statistics, not national ratings.
Custom stations are scoped to a country; older two-item records are migrated.
"""
from urllib.parse import urlsplit

COUNTRIES = (
    ("FR", "France"),
    ("BE", "Belgique"), ("CH", "Suisse"),
    ("GB", "Royaume-Uni"), ("DE", "Allemagne"),
    ("ES", "Espagne"), ("IT", "Italie"), ("PT", "Portugal"),
    ("NL", "Pays-Bas"), ("US", "États-Unis"),
    ("CA", "Canada"), ("RU", "Russie"),
    ("CN", "Chine"), ("JP", "Japon"),
    ("AU", "Australie"), ("PERSONAL", "Mes radios sans pays"),
)
COUNTRIES_EN = {
    "FR": "France", "BE": "Belgium", "CH": "Switzerland",
    "GB": "United Kingdom", "DE": "Germany", "ES": "Spain",
    "IT": "Italy", "PT": "Portugal", "NL": "Netherlands",
    "US": "United States", "CA": "Canada", "RU": "Russia",
    "CN": "China", "JP": "Japan", "AU": "Australia",
    "PERSONAL": "My uncategorized stations",
}
FRANCE_FEATURED = ("RTL", "Franceinfo", "France Inter", "FIP", "RMC")
COUNTRY_CODES = frozenset(code for code, _ in COUNTRIES)
FRENCH_KNOWN = frozenset(name.casefold() for name in (
    "RTL", "Franceinfo", "France Inter", "FIP", "RMC", "Europe 1",
    "NRJ", "Nostalgie", "Chérie FM", "RTL2", "France Culture",
    "France Musique", "RFM", "Skyrock", "Fun Radio",
))


def valid_stream_url(url):
    """Admit only absolute HTTP(S) station links."""
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        parsed = urlsplit(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        return False


def parse_directory_stations(items, limit=5):
    """Extract up to five unique stream entries from a directory response."""
    if not isinstance(items, list):
        return []
    stations = []
    seen = set()
    for item in items[:100]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        url = item.get("url_resolved") or item.get("url")
        if not valid_stream_url(url):
            url = item.get("url")
        if not name or len(name) > 65 or not valid_stream_url(url):
            continue
        normalized = name.casefold()
        if normalized in seen:
            continue
        homepage = item.get("homepage") or ""
        if not valid_stream_url(homepage):
            homepage = ""
        stations.append({"name": name, "url": url.strip(), "homepage": homepage})
        seen.add(normalized)
        if len(stations) >= limit:
            break
    return stations


def normalize_saved_stations(data):
    """Backwards compatibility for the legacy two-value [(name, url)] list."""
    return [(s["name"], s["url"]) for s in normalize_saved_stations_v2(data)]


def normalize_saved_stations_v2(data):
    """Validate/migrate saved custom stations into name/url/country dicts.

    Legacy France-branded stations go to France; other legacy stations become
    unclassified rather than being incorrectly shown in every country.
    """
    if not isinstance(data, list):
        return []
    result = []
    seen = set()
    for item in data[:250]:
        if isinstance(item, dict):
            name = item.get("name")
            url = item.get("url")
            country = item.get("country", "PERSONAL")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            name, url = item
            country = "FR" if isinstance(name, str) and name.strip().casefold() in FRENCH_KNOWN else "PERSONAL"
        else:
            continue
        if not isinstance(name, str) or not isinstance(country, str):
            continue
        name = name.strip()
        if not name or len(name) > 70 or not valid_stream_url(url):
            continue
        if country not in COUNTRY_CODES:
            country = "PERSONAL"
        identity = (name.casefold(), country)
        if identity in seen:
            continue
        result.append({"name": name, "url": url.strip(), "country": country})
        seen.add(identity)
    return result


def stations_for_country(custom_stations, code):
    """Return only stations explicitly associated with one country."""
    return [(item["name"], item["url"]) for item in custom_stations
            if item["country"] == code]

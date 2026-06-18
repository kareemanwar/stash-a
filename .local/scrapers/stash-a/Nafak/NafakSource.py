import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import Nafak


SCRAPER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRAPER_ROOT / "Shrmha"))
sys.modules["Shrmha"] = Nafak

import ShrmhaSource as BaseSource  # noqa: E402


def strip_tracking_query(query: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        key: value
        for key, value in query.items()
        if key not in {"fbclid", "gclid"} and not key.lower().startswith("utm_")
    }


def canonical_source_url(url: str) -> str:
    parsed = urlparse(url)
    query = strip_tracking_query(parse_qs(parsed.query, keep_blank_values=True))
    query.pop("paged", None)
    query.pop("page", None)
    path = re.sub(r"/page/\d+/?$", "/", parsed.path or "/")
    return urlunparse((parsed.scheme or "https", parsed.netloc or urlparse(Nafak.STUDIO_URL).netloc, path or "/", "", urlencode(query, doseq=True), ""))


def listing_page_url(seed_url: str, page_number: int) -> str:
    parsed = urlparse(canonical_source_url(seed_url))
    query = strip_tracking_query(parse_qs(parsed.query, keep_blank_values=True))
    path = parsed.path or "/"

    if "s" in query:
        if page_number > 1:
            query["paged"] = [str(page_number)]
        else:
            query.pop("paged", None)
            query.pop("page", None)
    else:
        query.pop("paged", None)
        query.pop("page", None)
        path = f"{path.rstrip('/')}/page/{page_number}/" if page_number > 1 else re.sub(r"/page/\d+/?$", "/", path)

    return urlunparse((parsed.scheme or "https", parsed.netloc or urlparse(Nafak.STUDIO_URL).netloc, path or "/", "", urlencode(query, doseq=True), ""))


def extract_source_title(url: str, document: str) -> str:
    query = BaseSource.extract_query(url, document)
    if query:
        return f"{query} - {Nafak.STUDIO_NAME}"
    title_match = re.search(r"<title[^>]*>(?P<title>.*?)</title>", document, re.IGNORECASE | re.DOTALL)
    title = BaseSource.strip_tags(title_match.group("title") if title_match else None)
    title = re.sub(r"\s+-\s+.*$", "", title).strip()
    return title or Nafak.STUDIO_NAME


def preview_only(_args: dict) -> bool:
    return False


BaseSource.canonical_source_url = canonical_source_url
BaseSource.listing_page_url = listing_page_url
BaseSource.extract_source_title = extract_source_title
BaseSource.get_hydrate_scenes_arg = preview_only
BaseSource.main()

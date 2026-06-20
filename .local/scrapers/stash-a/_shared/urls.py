from __future__ import annotations

from urllib.parse import parse_qs, urljoin, urlparse, urlunparse


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid"}


def absolute_url(base_url: str, url: str | None) -> str | None:
    if not url:
        return None
    return urljoin(base_url, url.strip())


def normalized_host(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def strip_tracking_query(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query = {
        key: values
        for key, values in query.items()
        if key not in TRACKING_QUERY_KEYS and not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    }
    from urllib.parse import urlencode

    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(query, doseq=True), ""))


def unique_strings(*groups: object) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if isinstance(group, str):
            items = [group]
        elif isinstance(group, list):
            items = [item for item in group if isinstance(item, str)]
        else:
            continue
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
    return result

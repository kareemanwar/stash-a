from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; Stash-a scraper framework)"


def http_safe_url(url: str) -> str:
    """Return a URL safe for urllib requests while preserving already-escaped bytes."""
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return url

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            quote(unquote(parsed.path), safe="/%"),
            quote(unquote(parsed.query), safe="=&?/:;+,%@"),
            "",
        )
    )


def safe_header_url(url: str | None) -> str | None:
    if not url:
        return None
    return http_safe_url(url)


def fetch_text(
    url: str,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
) -> str:
    request_headers = {"User-Agent": user_agent}
    if headers:
        request_headers.update({k: v for k, v in headers.items() if v is not None})

    request = Request(http_safe_url(url), headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        content_type_charset = response.headers.get_content_charset()
        body = response.read()

    for charset in (content_type_charset, "utf-8", "cp1256", "latin-1"):
        if not charset:
            continue
        try:
            return body.decode(charset, errors="replace")
        except LookupError:
            continue

    return body.decode("utf-8", errors="replace")

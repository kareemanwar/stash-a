import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (compatible; Stash-a Nafak scraper)"
STUDIO_NAME = "Nafak"
STUDIO_SLUG = "nafak"
STUDIO_URL = "https://nafakarab.com/"
SITE_TITLE_AR = "نفق السكس العربي"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.iframes: list[str] = []
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.time_datetimes: list[str] = []
        self._in_title = False
        self._in_h1 = False
        self._current_h1_id: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): v or "" for k, v in attrs}

        if tag == "meta":
            key = attr.get("property") or attr.get("name")
            content = attr.get("content")
            if key and content:
                self.meta[key] = content.strip()

        if tag == "link":
            rel = attr.get("rel", "").lower()
            href = attr.get("href")
            if rel and href:
                self.links[rel] = href.strip()

        if tag == "iframe":
            src = attr.get("src")
            if src:
                self.iframes.append(src.strip())

        if tag == "title":
            self._in_title = True

        if tag == "h1":
            self._in_h1 = True
            self._current_h1_id = attr.get("id")

        if tag == "time":
            datetime_value = attr.get("datetime")
            if datetime_value:
                self.time_datetimes.append(datetime_value.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
            self._current_h1_id = None

    def handle_data(self, data: str) -> None:
        text = clean_text(data)
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        if self._in_h1 and (self._current_h1_id in (None, "post-title")):
            self.h1_parts.append(text)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def write_json(value: Any) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=True))
    sys.stdout.write("\n")


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def first(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value


def find_jsonld_objects(data: Any) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if isinstance(data, dict):
        objects.append(data)
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                objects.extend(find_jsonld_objects(item))
    elif isinstance(data, list):
        for item in data:
            objects.extend(find_jsonld_objects(item))
    return objects


def extract_jsonld(document: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(document):
        raw = html.unescape(match.group(1)).strip()
        if not raw:
            continue
        try:
            results.extend(find_jsonld_objects(json.loads(raw)))
        except json.JSONDecodeError:
            continue
    return results


def pick_schema_object(objects: list[dict[str, Any]], schema_type: str) -> dict[str, Any]:
    for obj in objects:
        obj_type = obj.get("@type")
        if obj_type == schema_type or (isinstance(obj_type, list) and schema_type in obj_type):
            return obj
    return {}


def extract_tags(document: str, article: dict[str, Any]) -> list[dict[str, str]]:
    raw_keywords = article.get("keywords")
    names: list[str] = []

    if isinstance(raw_keywords, list):
        names.extend(clean_text(str(x)) for x in raw_keywords)
    elif isinstance(raw_keywords, str):
        names.extend(clean_text(x) for x in raw_keywords.split(","))

    if not names:
        tag_block = re.search(
            r'<div[^>]+class=["\'][^"\']*post-page-tags[^"\']*["\'][^>]*>(.*?)</div>',
            document,
            re.IGNORECASE | re.DOTALL,
        )
        if tag_block:
            names.extend(
                clean_text(re.sub(r"<[^>]+>", "", match.group(1)))
                for match in re.finditer(r"<a\b[^>]*>(.*?)</a>", tag_block.group(1), re.IGNORECASE | re.DOTALL)
            )

    seen: set[str] = set()
    tags: list[dict[str, str]] = []
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        tags.append({"name": name})
    return tags


def extract_external_id(page_url: str, canonical_url: str | None, document: str) -> str | None:
    for candidate in [canonical_url, page_url]:
        if not candidate:
            continue
        parsed = urlparse(candidate)
        query_id = first(parse_qs(parsed.query).get("p"))
        if query_id:
            return str(query_id)

    for pattern in [r"postid-(\d+)", r"wp-json/wp/v2/posts/(\d+)", r"post-(\d+)"]:
        post_id = re.search(pattern, document)
        if post_id:
            return post_id.group(1)

    return None


def normalize_date(value: str | None) -> str | None:
    value = clean_text(value)
    if not value:
        return None
    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
    if iso_match:
        return iso_match.group(1)
    return value


def strip_site_suffix(title: str) -> str:
    title = re.sub(rf"\s+-\s+{re.escape(SITE_TITLE_AR)}\s*$", "", title).strip()
    title = re.sub(r"\s+-\s+موقع\s+.*$", "", title).strip()
    return title


def parse_number(value: str) -> int | None:
    digits = re.sub(r"[^0-9]", "", value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def extract_view_count(document: str) -> int | None:
    patterns = [
        r"(?:views?|مشاهدات)\D{0,32}([0-9][0-9,\. ]*)",
        r"([0-9][0-9,\. ]*)\D{0,12}(?:views?|مشاهدات)",
    ]
    for pattern in patterns:
        match = re.search(pattern, document, re.IGNORECASE)
        if match:
            parsed = parse_number(match.group(1))
            if parsed is not None:
                return parsed
    return None


def append_stream(
    streams: list[dict[str, Any]],
    seen: set[str],
    *,
    url: str,
    label: str | None,
    kind: str,
    base_url: str,
) -> None:
    stream_url = urljoin(base_url, clean_text(url))
    if not stream_url or stream_url in seen:
        return
    seen.add(stream_url)
    streams.append(
        {
            "label": clean_text(label) or None,
            "kind": kind,
            "url": stream_url,
            "position": len(streams),
            "is_primary": len(streams) == 0,
        }
    )


def html_label(value: str | None) -> str | None:
    if not value:
        return None
    return clean_text(re.sub(r"<[^>]+>", " ", value)) or None


def extract_embed_streams(document: str, parser: PageParser, base_url: str) -> list[dict[str, Any]]:
    streams: list[dict[str, Any]] = []
    seen: set[str] = set()

    go_pattern = re.compile(
        r"<(?P<tag>[a-zA-Z0-9]+)\b(?P<attrs>[^>]*)\bonclick=[\"'][^\"']*\bgo\((?P<quote>[\"'])(?P<url>.*?)(?P=quote)\)[^\"']*[\"'][^>]*>(?P<label>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in go_pattern.finditer(document):
        append_stream(
            streams,
            seen,
            url=match.group("url"),
            label=html_label(match.group("label")),
            kind="embed",
            base_url=base_url,
        )

    for iframe_url in parser.iframes:
        append_stream(
            streams,
            seen,
            url=iframe_url,
            label="Primary embed" if not streams else "Embed",
            kind="embed",
            base_url=base_url,
        )

    return streams


def extract_direct_streams(document: str, base_url: str, streams: list[dict[str, Any]]) -> str | None:
    seen = {stream["url"] for stream in streams}
    direct_patterns = [
        r"<(?:video|source)\b[^>]+src=[\"'](?P<url>[^\"']+\.(?:mp4|m3u8)(?:\?[^\"']*)?)[\"']",
        r"[\"'](?P<url>https?://[^\"']+\.(?:mp4|m3u8)(?:\?[^\"']*)?)[\"']",
    ]

    first_direct: str | None = None
    for pattern in direct_patterns:
        for match in re.finditer(pattern, document, re.IGNORECASE):
            before = len(streams)
            append_stream(
                streams,
                seen,
                url=match.group("url"),
                label="Direct video" if first_direct is None else "Direct video alternate",
                kind="direct",
                base_url=base_url,
            )
            if len(streams) > before and first_direct is None:
                first_direct = streams[-1]["url"]
    return first_direct


def build_online_media(
    *,
    url: str,
    canonical_url: str,
    external_id: str | None,
    image: str | None,
    document: str,
    parser: PageParser,
) -> dict[str, Any]:
    streams = extract_embed_streams(document, parser, canonical_url)
    direct_video_url = extract_direct_streams(document, canonical_url, streams)
    embed_url = next((stream["url"] for stream in streams if stream["kind"] == "embed"), None)

    media: dict[str, Any] = {
        "source_name": STUDIO_NAME,
        "source_slug": STUDIO_SLUG,
        "external_id": external_id,
        "page_url": url,
        "canonical_url": canonical_url,
        "embed_url": embed_url,
        "direct_video_url": direct_video_url,
        "thumbnail_url": image,
        "duration_seconds": None,
        "external_view_count": extract_view_count(document),
        "streams": streams,
    }
    media["raw_metadata_json"] = json.dumps(
        {
            "source": STUDIO_SLUG,
            "external_id": external_id,
            "streams": streams,
        },
        ensure_ascii=True,
    )
    return media


def scrape_scene_by_url(url: str) -> dict[str, Any]:
    document = fetch_html(url)
    parser = PageParser()
    parser.feed(document)

    jsonld_objects = extract_jsonld(document)
    article = pick_schema_object(jsonld_objects, "Article")
    webpage = pick_schema_object(jsonld_objects, "WebPage")

    canonical_url = (
        parser.links.get("canonical")
        or clean_text(parser.meta.get("og:url"))
        or clean_text(webpage.get("url") if isinstance(webpage, dict) else None)
        or url
    )
    canonical_url = urljoin(url, canonical_url)

    title = (
        clean_text(article.get("headline"))
        or clean_text(parser.meta.get("og:title"))
        or clean_text(" ".join(parser.h1_parts))
        or strip_site_suffix(clean_text(" ".join(parser.title_parts)))
    )
    title = strip_site_suffix(title)

    description = (
        clean_text(parser.meta.get("og:description"))
        or clean_text(parser.meta.get("description"))
        or clean_text(webpage.get("description") if isinstance(webpage, dict) else None)
    )

    image = (
        clean_text(article.get("thumbnailUrl"))
        or clean_text(webpage.get("thumbnailUrl") if isinstance(webpage, dict) else None)
        or clean_text(parser.meta.get("og:image"))
    )
    if image:
        image = urljoin(canonical_url, image)

    date = normalize_date(
        clean_text(article.get("datePublished"))
        or clean_text(parser.meta.get("article:published_time"))
        or (parser.time_datetimes[0] if parser.time_datetimes else None)
    )

    external_id = extract_external_id(url, canonical_url, document)

    result: dict[str, Any] = {
        "title": title,
        "urls": [canonical_url],
        "studio": {
            "name": STUDIO_NAME,
            "urls": [STUDIO_URL],
            "remote_site_id": STUDIO_SLUG,
        },
        "tags": extract_tags(document, article),
        "online_media": build_online_media(
            url=url,
            canonical_url=canonical_url,
            external_id=external_id,
            image=image,
            document=document,
            parser=parser,
        ),
    }

    if description:
        result["details"] = description
    if date:
        result["date"] = date
    if image:
        result["image"] = image
    if external_id:
        result["remote_site_id"] = external_id

    return result


def scraper_args() -> tuple[str, dict[str, Any]]:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation", required=True)
    subparsers.add_parser("scene-by-url").add_argument("--url")
    args = vars(parser.parse_args())

    if not sys.stdin.isatty():
        try:
            args.update(json.load(sys.stdin))
        except json.JSONDecodeError:
            sys.exit(69)

    return args.pop("operation"), args


def get_url_arg(args: dict[str, Any]) -> str | None:
    url = args.get("url")
    if isinstance(url, str) and url:
        return url

    urls = args.get("urls")
    if isinstance(urls, list) and urls:
        first_url = urls[0]
        if isinstance(first_url, str) and first_url:
            return first_url

    return None


def main() -> None:
    operation, args = scraper_args()
    if operation == "scene-by-url":
        url = get_url_arg(args)
        if url:
            write_json(scrape_scene_by_url(url))
            return

    print(json.dumps({"error": f"Unsupported operation or missing URL: {operation}"}), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()

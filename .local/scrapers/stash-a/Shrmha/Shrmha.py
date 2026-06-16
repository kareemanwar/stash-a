import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 (compatible; Stash-a Shrmha scraper)"
STUDIO_NAME = "Shrmha"
STUDIO_URL = "https://shrmha.com/"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}
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

    post_id = re.search(r"postid-(\d+)", document)
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
    return re.sub(r"\s+-\s+شرمها\s*$", "", title).strip()


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

    result: dict[str, Any] = {
        "title": title,
        "urls": [canonical_url],
        "studio": {
            "name": STUDIO_NAME,
            "urls": [STUDIO_URL],
            "remote_site_id": "shrmha",
        },
        "tags": extract_tags(document, article),
    }

    if description:
        result["details"] = description
    if date:
        result["date"] = date
    if image:
        result["image"] = image

    external_id = extract_external_id(url, canonical_url, document)
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


def main() -> None:
    operation, args = scraper_args()
    if operation == "scene-by-url" and args.get("url"):
        print(json.dumps(scrape_scene_by_url(args["url"]), ensure_ascii=False))
        return

    print(json.dumps({"error": f"Unsupported operation: {operation}"}), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()

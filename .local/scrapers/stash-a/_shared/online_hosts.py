import html
import json
import re
from http.cookiejar import CookieJar
from typing import Any, Callable
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


UNAVAILABLE_PLAYER_MARKERS = (
    "file is no longer available",
    "expired or has been deleted",
    "file was deleted",
    "file has been deleted",
    "video has been deleted",
    "file not found",
)

CleanText = Callable[[str | None], str]


def html_label(value: str | None, clean_text: CleanText) -> str | None:
    if not value:
        return None

    label = re.sub(r"<[^>]+>", " ", value)
    return clean_text(label) or None


def js_string(value: str) -> str:
    return bytes(value, "utf-8").decode("unicode_escape").replace("\\/", "/")


def base_n(value: int, radix: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"

    result = ""
    while value:
        value, remainder = divmod(value, radix)
        result = digits[remainder] + result
    return result


def unpack_packed_scripts(document: str) -> list[str]:
    unpacked: list[str] = []
    packed_pattern = re.compile(
        r"eval\(function\(p,a,c,k,e,d\).*?\}\('(?P<p>(?:\\.|[^\\'])*)',(?P<a>\d+),(?P<c>\d+),'(?P<k>(?:\\.|[^\\'])*)'\.split\('\|'\)\)\)",
        re.IGNORECASE | re.DOTALL,
    )

    for match in packed_pattern.finditer(document):
        payload = js_string(match.group("p"))
        radix = int(match.group("a"))
        count = int(match.group("c"))
        keywords = js_string(match.group("k")).split("|")

        for index in range(count - 1, -1, -1):
            if index >= len(keywords) or not keywords[index]:
                continue

            token = base_n(index, radix)
            payload = re.sub(rf"\b{re.escape(token)}\b", keywords[index], payload)

        unpacked.append(payload)

    return unpacked


def is_unavailable_player_document(document: str) -> bool:
    text = re.sub(r"\s+", " ", html.unescape(document)).lower()
    return any(marker in text for marker in UNAVAILABLE_PLAYER_MARKERS)


def extract_xfilesharing_file_code(embed_url: str) -> str | None:
    parsed = urlparse(embed_url)
    path = parsed.path.rstrip("/")
    if not path:
        return None

    filename = path.split("/")[-1]

    legacy_match = re.match(r"embed-([^/?#]+?)(?:\.html)?$", filename, re.IGNORECASE)
    if legacy_match:
        return legacy_match.group(1)

    path_match = re.search(r"/(?:e|embed|iframe|player)/([^/?#]+)", path, re.IGNORECASE)
    if path_match:
        return path_match.group(1).removesuffix(".html")

    return filename.removeprefix("embed-").removesuffix(".html") or None


def fetch_xfilesharing_player_document(
    embed_url: str,
    page_url: str,
    user_agent: str,
) -> tuple[str | None, bool]:
    """Return player document and whether the embed is confirmed unavailable."""

    parsed = urlparse(embed_url)
    if not parsed.scheme or not parsed.netloc:
        return None, False

    origin = f"{parsed.scheme}://{parsed.netloc}"
    file_code = extract_xfilesharing_file_code(embed_url)
    if not file_code:
        return None, False

    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    get_request = Request(
        embed_url,
        headers={
            "User-Agent": user_agent,
            "Referer": page_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with opener.open(get_request, timeout=30) as response:
            embed_document = response.read().decode(
                response.headers.get_content_charset() or "utf-8",
                errors="replace",
            )
    except Exception:
        return None, False

    if is_unavailable_player_document(embed_document):
        return None, True

    documents = [embed_document]
    data = urlencode(
        {
            "op": "embed",
            "file_code": file_code,
            "auto": "1",
            "referer": page_url,
        }
    ).encode("utf-8")

    post_request = Request(
        urljoin(origin, "/dl"),
        data=data,
        headers={
            "User-Agent": user_agent,
            "Referer": embed_url,
            "Origin": origin,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="POST",
    )

    try:
        with opener.open(post_request, timeout=30) as response:
            player_document = response.read().decode(
                response.headers.get_content_charset() or "utf-8",
                errors="replace",
            )
    except Exception:
        return "\n".join(documents), False

    if is_unavailable_player_document(player_document):
        return None, True

    documents.append(player_document)
    return "\n".join(documents), False


def fetch_text(url: str, referer: str, user_agent: str) -> str | None:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Referer": referer,
            "Accept": "*/*",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode(
                response.headers.get_content_charset() or "utf-8",
                errors="replace",
            )
    except Exception:
        return None


def parse_hls_max_height(playlist: str) -> int | None:
    heights: list[int] = []

    for match in re.finditer(r"RESOLUTION=\d+x(?P<height>\d+)", playlist, re.IGNORECASE):
        try:
            heights.append(int(match.group("height")))
        except ValueError:
            continue

    return max(heights) if heights else None


def probe_direct_quality(direct_url: str, referer: str, user_agent: str) -> int | None:
    if not re.search(r"\.m3u8(?:\?|$)", direct_url, re.IGNORECASE):
        return None

    playlist = fetch_text(direct_url, referer, user_agent)
    if not playlist:
        return None

    return parse_hls_max_height(playlist)


def parse_seconds(value: str) -> int | None:
    value = value.strip().strip('"\'')
    if not value:
        return None

    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        seconds = round(float(value))
        return seconds if seconds > 5 else None

    time_match = re.fullmatch(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})", value)
    if time_match:
        hours = int(time_match.group(1) or 0)
        minutes = int(time_match.group(2))
        seconds = int(time_match.group(3))
        total = hours * 3600 + minutes * 60 + seconds
        return total if total > 5 else None

    return None


def extract_player_metadata(
    player_document: str,
    base_url: str,
    user_agent: str,
) -> tuple[str | None, int | None, int | None]:
    documents = [player_document]
    documents.extend(unpack_packed_scripts(player_document))
    joined = "\n".join(html.unescape(doc) for doc in documents)

    direct_url: str | None = None
    direct_patterns = [
        r"https?://[^\"'<>\\\s]+?\.(?:mp4|m3u8)(?:\?[^\"'<>\\\s]*)?",
        r"[\"']file[\"']\s*:\s*[\"']([^\"']+)[\"']",
        r"[\"']src[\"']\s*:\s*[\"']([^\"']+)[\"']",
        r"<source\b[^>]+src=[\"']([^\"']+)[\"']",
    ]

    for pattern in direct_patterns:
        for match in re.finditer(pattern, joined, re.IGNORECASE):
            candidate = match.group(1) if match.groups() else match.group(0)
            if re.search(r"\.(?:mp4|m3u8)(?:\?|$)", candidate, re.IGNORECASE):
                direct_url = urljoin(base_url, candidate)
                break

        if direct_url:
            break

    duration_seconds: int | None = None
    duration_patterns = [
        r"[\"']duration[\"']\s*:\s*[\"']?([^,\"'\}\]\s]+)",
        r"\bduration\s*[:=]\s*[\"']?([^,\"'\}\]\s]+)",
        r"[\"']length[\"']\s*:\s*[\"']?([^,\"'\}\]\s]+)",
        r"(\d{1,2}:\d{2}(?::\d{2})?)",
    ]

    for pattern in duration_patterns:
        for match in re.finditer(pattern, joined, re.IGNORECASE):
            parsed = parse_seconds(match.group(1))
            if parsed:
                duration_seconds = parsed
                break

        if duration_seconds:
            break

    quality_height = probe_direct_quality(direct_url, base_url, user_agent) if direct_url else None
    return direct_url, duration_seconds, quality_height


def quality_label(label: str | None, height: int | None, clean_text: CleanText) -> str:
    base = clean_text(label) or "Direct video"
    if height and f"{height}p" not in base:
        return f"{base} · {height}p"

    return base


def reset_stream_order(streams: list[dict[str, Any]]) -> None:
    for index, stream in enumerate(streams):
        stream["position"] = index
        stream["is_primary"] = index == 0


def enhance_online_media(
    media: dict[str, Any],
    page_url: str,
    *,
    user_agent: str,
    source_slug: str,
    clean_text: CleanText,
    max_embed_probes: int = 8,
) -> dict[str, Any]:
    streams = media.get("streams")
    if not isinstance(streams, list):
        return media

    available_direct_streams: list[tuple[int, int, dict[str, Any]]] = []
    available_embed_streams: list[dict[str, Any]] = []
    unavailable_streams: list[dict[str, Any]] = []
    seen_direct_urls: set[str] = set()
    duration_seconds: int | None = media.get("duration_seconds")

    for source_index, stream in enumerate(list(streams)[:max_embed_probes]):
        if not isinstance(stream, dict) or stream.get("kind") != "embed":
            continue

        embed_url = stream.get("url")
        if not isinstance(embed_url, str) or not embed_url:
            continue

        player_document, confirmed_unavailable = fetch_xfilesharing_player_document(
            embed_url,
            page_url,
            user_agent,
        )
        if confirmed_unavailable:
            unavailable_streams.append(stream)
            continue

        available_embed_streams.append(stream)

        if not player_document:
            continue

        direct_url, parsed_duration, quality_height = extract_player_metadata(
            player_document,
            embed_url,
            user_agent,
        )
        if parsed_duration and not duration_seconds:
            duration_seconds = parsed_duration

        if not direct_url or direct_url in seen_direct_urls:
            continue

        seen_direct_urls.add(direct_url)
        available_direct_streams.append(
            (
                quality_height or 0,
                source_index,
                {
                    "label": quality_label(stream.get("label"), quality_height, clean_text),
                    "kind": "direct",
                    "url": direct_url,
                    "position": 0,
                    "is_primary": False,
                },
            )
        )

    if available_direct_streams:
        available_direct_streams.sort(key=lambda item: (-item[0], item[1]))
        direct_streams = [stream for _, _, stream in available_direct_streams]
        fallback_streams = available_embed_streams or [
            stream for stream in streams if isinstance(stream, dict) and stream not in unavailable_streams
        ]

        streams = direct_streams + fallback_streams
        reset_stream_order(streams)
        media["streams"] = streams
        media["direct_video_url"] = direct_streams[0]["url"]
        media["embed_url"] = fallback_streams[0].get("url") if fallback_streams else media.get("embed_url")
    else:
        fallback_streams = available_embed_streams or [
            stream for stream in streams if isinstance(stream, dict) and stream not in unavailable_streams
        ]

        reset_stream_order(fallback_streams)
        media["streams"] = fallback_streams
        media["direct_video_url"] = None
        media["embed_url"] = next(
            (stream.get("url") for stream in fallback_streams if stream.get("kind") == "embed"),
            None,
        )

    if duration_seconds:
        media["duration_seconds"] = duration_seconds

    media["raw_metadata_json"] = json.dumps(
        {
            "source": source_slug,
            "external_id": media.get("external_id"),
            "direct_video_url": media.get("direct_video_url"),
            "duration_seconds": media.get("duration_seconds"),
            "streams": media.get("streams"),
            "unavailable_streams": unavailable_streams,
        },
        ensure_ascii=True,
    )
    return media


def remove_internal_online_media_fields(media: dict[str, Any]) -> dict[str, Any]:
    media.pop("page_url", None)
    media.pop("canonical_url", None)
    return media

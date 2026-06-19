import html
import json
import re
import shutil
import subprocess
from http.cookiejar import CookieJar
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
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



STREAMTAPE_HOST_MARKER = "streamtape"


def is_streamtape_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return STREAMTAPE_HOST_MARKER in host


def fetch_streamtape_player_document(
    embed_url: str,
    page_url: str,
    user_agent: str,
) -> tuple[str | None, bool]:
    """Return Streamtape player document and whether it is confirmed unavailable."""

    parsed = urlparse(embed_url)
    if not parsed.scheme or not parsed.netloc:
        return None, False

    request = Request(
        embed_url,
        headers={
            "User-Agent": user_agent,
            "Referer": page_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            document = response.read().decode(
                response.headers.get_content_charset() or "utf-8",
                errors="replace",
            )
    except Exception:
        return None, False

    if is_unavailable_player_document(document):
        return None, True

    return document, False



def normalize_streamtape_direct_url(candidate: str, base_url: str) -> str | None:
    candidate = html.unescape(candidate or "")
    candidate = candidate.replace("\\/", "/").replace("\\u0026", "&")
    candidate = candidate.strip().strip('"\'')
    candidate = re.sub(r"\s+", "", candidate)

    if not candidate:
        return None

    if candidate.startswith("//"):
        candidate = "https:" + candidate
    elif candidate.startswith("/streamtape.com/"):
        candidate = "https:/" + candidate
    elif candidate.startswith("streamtape.com/"):
        candidate = "https://" + candidate
    elif candidate.startswith("/get_video?"):
        candidate = urljoin(base_url, candidate)
    else:
        candidate = urljoin(base_url, candidate)

    parsed = urlparse(candidate)
    if STREAMTAPE_HOST_MARKER not in parsed.netloc.lower():
        return None
    if "get_video" not in parsed.path:
        return None

    query = parse_qs(parsed.query, keep_blank_values=True)
    video_id = (query.get("id") or [""])[0].strip()
    if not video_id or video_id.lower() in {"undefined", "null", "none"}:
        return None

    has_token = bool((query.get("token") or [""])[0].strip())
    has_expires = bool((query.get("expires") or [""])[0].strip())
    if not (has_token or has_expires):
        return None

    return candidate



def streamtape_embed_id(base_url: str) -> str | None:
    path = urlparse(base_url).path
    match = re.search(r"/(?:e|v)/([^/?#]+)", path, re.IGNORECASE)
    return match.group(1) if match else None


def streamtape_direct_url_score(url: str, base_url: str) -> int:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    score = 0

    embed_id = streamtape_embed_id(base_url)
    video_id = (query.get("id") or [""])[0]
    if embed_id and video_id == embed_id:
        score += 1000
    if (query.get("token") or [""])[0]:
        score += 200
    if (query.get("expires") or [""])[0]:
        score += 100
    if (query.get("ip") or [""])[0]:
        score += 50
    if parsed.scheme == "https":
        score += 10

    return score


def apply_javascript_substrings(value: str, ops: str) -> str:
    value = js_string(value)
    for match in re.finditer(r"\.substring\((\d+)\)", ops or ""):
        value = value[int(match.group(1)) :]
    return value


def reconstruct_javascript_string_expression(expression: str) -> str:
    """Reconstruct simple Streamtape JS string concatenation expressions.

    Streamtape commonly hides direct URLs as:
      'prefix' + ('noisevideo?...').substring(4)

    The substring calls may appear after a closing parenthesis, not directly
    after the string literal, so a simple quoted-string regex is not enough.
    """

    pieces: list[str] = []
    index = 0
    length = len(expression)

    while index < length:
        quote_index = -1
        quote_char = ""
        for candidate_quote in ("'", '"'):
            candidate_index = expression.find(candidate_quote, index)
            if candidate_index != -1 and (quote_index == -1 or candidate_index < quote_index):
                quote_index = candidate_index
                quote_char = candidate_quote

        if quote_index == -1:
            break

        value_chars: list[str] = []
        cursor = quote_index + 1
        escaped = False

        while cursor < length:
            char = expression[cursor]
            if escaped:
                value_chars.append("\\" + char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote_char:
                break
            else:
                value_chars.append(char)
            cursor += 1

        if cursor >= length:
            break

        after_quote = cursor + 1
        probe = after_quote

        # Dynamic Streamtape fragments are often wrapped in parentheses:
        # ('xyzavideo?...').substring(4)
        while probe < length and expression[probe].isspace():
            probe += 1
        if probe < length and expression[probe] == ")":
            probe += 1

        ops_start = probe
        while True:
            while probe < length and expression[probe].isspace():
                probe += 1
            prefix = ".substring("
            if not expression.startswith(prefix, probe):
                break
            probe += len(prefix)
            while probe < length and expression[probe].isdigit():
                probe += 1
            if probe < length and expression[probe] == ")":
                probe += 1
            else:
                break

        ops = expression[ops_start:probe]
        pieces.append(apply_javascript_substrings("".join(value_chars), ops))
        index = probe

    return "".join(pieces)


def add_streamtape_candidate(
    candidates: list[str],
    seen: set[str],
    candidate: str | None,
    base_url: str,
) -> None:
    if not candidate:
        return

    normalized = normalize_streamtape_direct_url(candidate, base_url)
    if not normalized or normalized in seen:
        return

    seen.add(normalized)
    candidates.append(normalized)


def extract_streamtape_direct_urls(player_document: str, base_url: str) -> list[str]:
    documents = [player_document]
    documents.extend(unpack_packed_scripts(player_document))
    joined = "\n".join(html.unescape(doc) for doc in documents).replace("\\/", "/")

    candidates: list[str] = []
    seen: set[str] = set()

    assignment_pattern = re.compile(
        r"document\.getElementById\(['\"](?:ideoolink|botlink|robotlink)['\"]\)\.innerHTML\s*=\s*(?P<expr>.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    for match in assignment_pattern.finditer(joined):
        reconstructed = reconstruct_javascript_string_expression(match.group("expr"))
        add_streamtape_candidate(candidates, seen, reconstructed, base_url)

    hidden_pattern = re.compile(
        r"<(?:div|span)\b[^>]+id=[\"'](?:ideoolink|botlink|robotlink)[\"'][^>]*>\s*(?P<url>[^<]+?)\s*</(?:div|span)>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in hidden_pattern.finditer(joined):
        add_streamtape_candidate(candidates, seen, match.group("url"), base_url)

    url_patterns = [
        r"(?P<url>https?://[^\"'<>\\\s]+/get_video\?[^\"'<>\\\s]+)",
        r"(?P<url>//[^\"'<>\\\s]+/get_video\?[^\"'<>\\\s]+)",
        r"(?P<url>/streamtape\.com/get_video\?[^\"'<>\\\s]+)",
        r"(?P<url>/get_video\?[^\"'<>\\\s]+)",
    ]
    for pattern in url_patterns:
        for match in re.finditer(pattern, joined, re.IGNORECASE):
            add_streamtape_candidate(candidates, seen, match.group("url"), base_url)

    candidates.sort(key=lambda url: streamtape_direct_url_score(url, base_url), reverse=True)
    return candidates


def extract_streamtape_direct_url(player_document: str, base_url: str) -> str | None:
    urls = extract_streamtape_direct_urls(player_document, base_url)
    return urls[0] if urls else None


FFPROBE_TIMEOUT_SECONDS = 12


def ffprobe_binary() -> str | None:
    return shutil.which("ffprobe")


def probe_media_metadata_with_ffprobe(
    direct_url: str,
    referer: str,
    user_agent: str,
) -> tuple[int | None, int | None]:
    """Probe direct media URL with ffprobe when available.

    ffprobe is optional. Scraping must continue if it is missing or if probing
    fails because direct media URLs can be short-lived or host-protected.
    """

    binary = ffprobe_binary()
    if not binary:
        return None, None

    headers = f"Referer: {referer}\r\nUser-Agent: {user_agent}\r\n"
    command = [
        binary,
        "-v",
        "error",
        "-hide_banner",
        "-user_agent",
        user_agent,
        "-headers",
        headers,
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        direct_url,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception:
        return None, None

    if result.returncode != 0 or not result.stdout.strip():
        return None, None

    try:
        payload = json.loads(result.stdout)
    except Exception:
        return None, None

    duration_seconds: int | None = None
    duration_value = (payload.get("format") or {}).get("duration")
    if duration_value is not None:
        try:
            parsed_duration = round(float(duration_value))
            if parsed_duration > 5:
                duration_seconds = parsed_duration
        except (TypeError, ValueError):
            pass

    heights: list[int] = []
    for stream in payload.get("streams") or []:
        if stream.get("codec_type") != "video":
            continue

        height = stream.get("height")
        try:
            if height:
                heights.append(int(height))
        except (TypeError, ValueError):
            continue

    quality_height = max(heights) if heights else None
    return duration_seconds, quality_height

def extract_streamtape_player_metadata(
    player_document: str,
    base_url: str,
    user_agent: str,
) -> tuple[str | None, int | None, int | None]:
    documents = [player_document]
    documents.extend(unpack_packed_scripts(player_document))
    joined = "\n".join(html.unescape(doc) for doc in documents)

    direct_urls = extract_streamtape_direct_urls(player_document, base_url)
    direct_url = direct_urls[0] if direct_urls else None

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

    quality_height: int | None = None
    probeable_direct_url: str | None = None
    for candidate_url in direct_urls:
        probed_duration, probed_height = probe_media_metadata_with_ffprobe(
            candidate_url,
            base_url,
            user_agent,
        )
        if probed_duration or probed_height:
            probeable_direct_url = candidate_url
            if probed_duration and not duration_seconds:
                duration_seconds = probed_duration
            if probed_height:
                quality_height = probed_height
            break

    # Streamtape may expose get_video candidates that currently return JSON/HTML
    # errors instead of media. Do not publish broken direct URLs; keep the embed
    # fallback unless a candidate is probeable as real media.
    return probeable_direct_url, duration_seconds, quality_height

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

        streamtape_embed = is_streamtape_url(embed_url)
        if streamtape_embed:
            player_document, confirmed_unavailable = fetch_streamtape_player_document(
                embed_url,
                page_url,
                user_agent,
            )
        else:
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

        if streamtape_embed:
            direct_url, parsed_duration, quality_height = extract_streamtape_player_metadata(
                player_document,
                embed_url,
                user_agent,
            )
        else:
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

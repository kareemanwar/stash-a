#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import difflib
import re

ROOT = Path.cwd()
BASE = ROOT / ".local" / "scrapers" / "stash-a"

FILES = [
    BASE / "T7tAl7zam" / "T7tAl7zam.yml",
    BASE / "T7tAl7zam" / "T7tAl7zam.py",
    BASE / "T7tAl7zam" / "T7tAl7zamSource.py",
    BASE / "Shrmha" / "Shrmha.yml",
    BASE / "Shrmha" / "Shrmha.py",
    BASE / "Shrmha" / "ShrmhaSource.py",
    BASE / "Nafak" / "Nafak.py",
]

KEY_PATTERNS = [
    "sys.stdin",
    "json.load",
    "json.loads",
    "def main",
    "if __name__",
    "thumbnailUrl",
    "og:image",
    "twitter:image",
    "poster",
    "data-src",
    "srcset",
    "result[\"image\"]",
    "'image'",
    '"image"',
    "extract_source_thumbnail",
    "extract_source_items",
    "sceneByURL",
    "sceneByFragment",
]

def read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()

def print_context(path: Path, line_no: int, radius: int = 8) -> None:
    lines = read(path)
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    print(f"\n--- {path.relative_to(ROOT)} L{start}-L{end}")
    for i in range(start, end + 1):
        print(f"{i:04d}: {lines[i-1]}")

def grep_context(path: Path) -> None:
    print(f"\n\n================ {path.relative_to(ROOT)} ================")
    if not path.exists():
        print("MISSING")
        return

    lines = read(path)
    hits: list[int] = []
    for i, line in enumerate(lines, 1):
        low = line.lower()
        if any(p.lower() in low for p in KEY_PATTERNS):
            hits.append(i)

    if not hits:
        print("No key pattern hits.")
        return

    printed_ranges: list[tuple[int, int]] = []
    for line_no in hits:
        start = max(1, line_no - 5)
        end = min(len(lines), line_no + 5)
        if printed_ranges and start <= printed_ranges[-1][1] + 2:
            printed_ranges[-1] = (printed_ranges[-1][0], max(printed_ranges[-1][1], end))
        else:
            printed_ranges.append((start, end))

    for start, end in printed_ranges:
        print(f"\n--- L{start}-L{end}")
        for i in range(start, end + 1):
            print(f"{i:04d}: {lines[i-1]}")

def normalized_for_diff(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.replace("T7tAl7zam", "SITE")
    text = text.replace("Shrmha", "SITE")
    text = text.replace("t7tal7zam", "site")
    text = text.replace("shrmha", "site")
    text = re.sub(r"https?://[^\"'\\s]+", "URL", text)
    return text.splitlines(keepends=True)

def main() -> int:
    print("ROOT:", ROOT)
    print("SCRAPER BASE:", BASE)

    for path in FILES:
        grep_context(path)

    t7t = BASE / "T7tAl7zam" / "T7tAl7zam.py"
    shr = BASE / "Shrmha" / "Shrmha.py"
    if t7t.exists() and shr.exists():
        print("\n\n================ normalized diff: T7tAl7zam.py vs Shrmha.py ================")
        diff = difflib.unified_diff(
            normalized_for_diff(shr),
            normalized_for_diff(t7t),
            fromfile="Shrmha.py normalized",
            tofile="T7tAl7zam.py normalized",
            n=3,
        )
        kept = []
        for line in diff:
            low = line.lower()
            if (
                line.startswith("@@")
                or "image" in low
                or "thumb" in low
                or "og:" in low
                or "thumbnailurl" in low
                or "canonical" in low
                or "urljoin" in low
                or "return" in low
                or "result" in low
            ):
                kept.append(line.rstrip("\n"))
        if kept:
            print("\n".join(kept[:400]))
        else:
            print("No relevant normalized diff around image/thumbnail paths.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())

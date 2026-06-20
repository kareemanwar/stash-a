#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path.cwd()
SCRAPER_ROOTS = [
    ROOT / ".local" / "scrapers" / "stash-a",
    ROOT / "scrapers",
    ROOT / "stash-a-scrapers",
]

THUMB_WORDS = [
    "image",
    "image_url",
    "thumbnail",
    "thumb",
    "poster",
    "cover",
    "og:image",
    "twitter:image",
]

TARGET_HINTS = [
    "تحت",
    "الحزام",
    "t7t",
    "ta7t",
    "hezzam",
    "7ezzam",
    "belt",
]

KNOWN_OK_HINTS = [
    "shrmha",
    "sharmha",
    "nafak",
]

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")

def line_hits(text: str, words: list[str]) -> list[tuple[int, str]]:
    out = []
    low_words = [w.lower() for w in words]
    for i, line in enumerate(text.splitlines(), 1):
        l = line.lower()
        if any(w in l for w in low_words):
            out.append((i, line.rstrip()))
    return out

def returned_dict_keys_from_python(text: str) -> list[list[str]]:
    results = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            keys = []
            for k in node.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.append(k.value)
            if keys:
                results.append(keys)
    return results

def classify(path: Path, text: str) -> str:
    s = f"{path.as_posix()}\n{text[:2000]}".lower()
    if any(h.lower() in s for h in TARGET_HINTS):
        return "TARGET_UNDER_BELT"
    if any(h.lower() in s for h in KNOWN_OK_HINTS):
        return "KNOWN_OK_REFERENCE"
    return "OTHER"

def main() -> int:
    roots = [p for p in SCRAPER_ROOTS if p.exists()]
    print("=== scraper roots found ===")
    for r in roots:
        print(r)

    if not roots:
        print("No scraper roots found. Expected one of:")
        for r in SCRAPER_ROOTS:
            print(" -", r)
        return 2

    files = []
    for root in roots:
        files.extend(sorted(root.rglob("*.py")))
        files.extend(sorted(root.rglob("*.yml")))
        files.extend(sorted(root.rglob("*.yaml")))

    print(f"\n=== files scanned: {len(files)} ===")

    report = []
    for path in files:
        text = read_text(path)
        thumb_hits = line_hits(text, THUMB_WORDS)
        target_class = classify(path, text)

        py_return_keys = []
        if path.suffix == ".py":
            py_return_keys = returned_dict_keys_from_python(text)

        suspicious = False
        reason = []

        lower = text.lower()
        looks_scene_scraper = any(x in lower for x in [
            "scrapedscene",
            "scene",
            "def scrape",
            "def scene",
            "return {",
        ])

        has_thumb_mapping = bool(thumb_hits)

        if looks_scene_scraper and not has_thumb_mapping:
            suspicious = True
            reason.append("looks like scene scraper but no thumbnail/image words")

        if target_class == "TARGET_UNDER_BELT":
            suspicious = True
            reason.append("matches under-belt target hints")

        item = {
            "path": str(path.relative_to(ROOT)),
            "class": target_class,
            "looks_scene_scraper": looks_scene_scraper,
            "has_thumb_mapping": has_thumb_mapping,
            "suspicious": suspicious,
            "reason": reason,
            "thumb_hits": thumb_hits[:25],
            "python_return_dict_keys": py_return_keys[:20],
        }
        report.append(item)

    print("\n=== suspicious / target files ===")
    for item in report:
        if item["suspicious"] or item["class"] != "OTHER":
            print("\n---", item["path"])
            print("class:", item["class"])
            print("looks_scene_scraper:", item["looks_scene_scraper"])
            print("has_thumb_mapping:", item["has_thumb_mapping"])
            if item["reason"]:
                print("reason:", "; ".join(item["reason"]))
            if item["python_return_dict_keys"]:
                print("return dict keys:")
                for keys in item["python_return_dict_keys"][:8]:
                    print(" ", keys)
            if item["thumb_hits"]:
                print("thumbnail-related lines:")
                for ln, line in item["thumb_hits"][:12]:
                    print(f"  L{ln}: {line}")

    out = ROOT / "scripts" / "dev" / "scraper_thumbnail_audit_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote JSON report: {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

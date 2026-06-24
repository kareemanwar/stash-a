#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import import_source_candidate_scenes as importer  # noqa: E402

importer.SCRAPERS["egyzeb"] = {
    "name": "EgyZeb",
    "source": "EgyZeb/scraper.py",
    "scene": "EgyZeb/EgyZebOnline.py",
}


def main() -> int:
    if "--scraper" not in sys.argv:
        sys.argv[1:1] = ["--scraper", "egyzeb"]
    return importer.main()


if __name__ == "__main__":
    raise SystemExit(main())

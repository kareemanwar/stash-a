#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import import_source_candidate_scenes as importer  # noqa: E402

importer.SCRAPERS["arabgy"] = {
    "name": "Arabgy",
    "source": "Arabgy/scraper.py",
    "scene": "Arabgy/ArabgyOnline.py",
}


def main() -> int:
    if "--scraper" not in sys.argv:
        sys.argv[1:1] = ["--scraper", "arabgy"]
    return importer.main()


if __name__ == "__main__":
    raise SystemExit(main())

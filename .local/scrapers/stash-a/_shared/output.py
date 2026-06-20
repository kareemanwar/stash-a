from __future__ import annotations

import json
import sys
from typing import Any


def drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if v not in (None, "", [], {})}


def raw_metadata(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def write_json(value: Any) -> None:
    # Stash reads scraper stdout as JSON. ASCII escaping avoids Windows console
    # encoding failures when metadata contains non-ASCII text.
    sys.stdout.write(json.dumps(value, ensure_ascii=True))
    sys.stdout.write("\n")

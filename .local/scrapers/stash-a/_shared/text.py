from __future__ import annotations

import html
import re


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(value))).strip()


def strip_tags(value: str | None) -> str:
    if not value:
        return ""
    return clean_text(re.sub(r"<[^>]+>", " ", value))


def attr_value(attrs: str, name: str) -> str | None:
    pattern = rf"\b{re.escape(name)}\s*=\s*([\"'])(?P<value>.*?)(?:\1)"
    match = re.search(pattern, attrs, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    value = html.unescape(match.group("value")).strip()
    return value or None


def first_non_empty(*values: object) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def unique_dicts_by_name(names: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_name in names:
        name = clean_text(raw_name)
        if not name or name in seen:
            continue
        seen.add(name)
        out.append({"name": name})
    return out

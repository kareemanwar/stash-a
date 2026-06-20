from __future__ import annotations

import html
import json
import re
from typing import Any


def flatten_jsonld(value: Any) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if isinstance(value, dict):
        objects.append(value)
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                objects.extend(flatten_jsonld(item))
    elif isinstance(value, list):
        for item in value:
            objects.extend(flatten_jsonld(item))
    return objects


def extract_jsonld(document: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for match in re.finditer(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(?P<body>.*?)</script>',
        document,
        re.IGNORECASE | re.DOTALL,
    ):
        raw = html.unescape(match.group("body")).strip()
        if not raw:
            continue
        try:
            objects.extend(flatten_jsonld(json.loads(raw)))
        except json.JSONDecodeError:
            continue
    return objects


def has_schema_type(obj: dict[str, Any], schema_type: str) -> bool:
    obj_type = obj.get("@type")
    if obj_type == schema_type:
        return True
    if isinstance(obj_type, list) and schema_type in obj_type:
        return True
    return False


def first_object(objects: list[dict[str, Any]], schema_type: str) -> dict[str, Any]:
    for obj in objects:
        if has_schema_type(obj, schema_type):
            return obj
    return {}


def first_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item:
                return item
    return None

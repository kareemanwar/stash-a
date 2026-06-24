#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import scraper as EgyZeb

sys.path.append(str(Path(__file__).resolve().parents[1]))

from _shared.online_hosts import enhance_online_media, remove_internal_online_media_fields  # noqa: E402


_ORIGINAL = EgyZeb.scrape_scene_by_url


def scrape_scene_by_url(url: str) -> dict[str, Any]:
    scene = _ORIGINAL(url)
    media = scene.get("online_media")
    if isinstance(media, dict):
        media = enhance_online_media(
            media,
            url,
            user_agent=EgyZeb.USER_AGENT,
            source_slug=EgyZeb.SOURCE_SLUG,
            clean_text=EgyZeb.clean_text,
        )
        scene["online_media"] = remove_internal_online_media_fields(media)
    return scene


EgyZeb.scrape_scene_by_url = scrape_scene_by_url
EgyZeb.main()

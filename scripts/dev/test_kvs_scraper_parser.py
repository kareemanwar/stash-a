#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRAPER_ROOT = ROOT / ".local" / "scrapers" / "stash-a"
sys.path.insert(0, str(SCRAPER_ROOT))

from _shared.profiles.kvs import parse_scene_page, parse_source_page  # noqa: E402


SCENE_HTML = """
<html>
<head>
<link href="https://example.test/videos/sample-scene/" rel="canonical"/>
<meta property="og:title" content="Studio Name - Sample Scene | Free"/>
<meta property="og:image" content="https://cdn.example.test/93788000/93788872/medium.jpg"/>
<meta property="og:description" content="Sample description."/>
<meta property="video:release_date" content="2024-07-01T18:18:30Z"/>
<meta property="video:duration" content="2694"/>
<meta property="video:tag" content="Sample Tag"/>
<script>var pageContext = { videoId: '93788872' };</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"VideoObject","name":"Studio Name - Sample Scene","duration":"PT0H44M54S","embedUrl":"https://example.test/embed/93788872","interactionStatistic":[{"@type":"InteractionCounter","interactionType":"http://schema.org/WatchAction","userInteractionCount":"4875"}]}
</script>
</head>
<body>
<a href="https://example.test/models/">Directory</a>
<div class="scene-metadata">
  <a href="https://example.test/sites/sample-studio/">Sample Studio</a>
  <a href="https://example.test/models/person-one/">Person One</a>
  <a href="https://example.test/models/person-two/">Person Two</a>
</div>
<div class="item">
  <a href="https://example.test/videos/related-card/" title="Related Card"><strong class="title">Related Card</strong></a>
  <div class="models">
    <a class="models__item" href="https://example.test/models/related-person/"><span>Related Person</span></a>
  </div>
</div>
<video>
<source src="https://media.example.test/get_file/93788872_720p.mp4/" type="video/mp4" label="720p">
<source src="https://media.example.test/get_file/93788872_2160p.mp4/" type="video/mp4" label="2160p">
</video>
</body>
</html>
"""

LIST_HTML = """
<html>
<head><link href="https://example.test/search/sample/relevance/" rel="canonical"/></head>
<body>
<div class="item">
  <a href="https://example.test/videos/sample-card/" target="_blank" title="Sample Card Title">
    <div class="img thumb__img" data-preview="https://preview.example.test/preview/93784844.mp4">
      <img class="thumb lazyload" data-src="https://cdn.example.test/93784000/93784844/medium.jpg" alt="Sample Card Title">
      <span class="duration"> Runtime 44:32 </span>
    </div>
  </a>
  <div class="item-info">
    <a href="https://example.test/videos/sample-card/" title="Sample Card Title">
      <strong class="title"> Sample Card Title </strong>
    </a>
    <div class="models">
      <a class="models__item thumb_cs" href="https://example.test/sites/card-studio/"><span>Card Studio</span></a>
      <a class="models__item" href="https://example.test/models/card-person/"><span>Card Person</span></a>
    </div>
  </div>
</div>
<div class="pagination"><a href="https://example.test/search/sample/relevance/2/">2</a></div>
</body>
</html>
"""


def main() -> None:
    scene = parse_scene_page(
        SCENE_HTML,
        "https://example.test/videos/sample-scene/",
        source_name="Example",
        source_slug="example",
        source_url="https://example.test/",
    )

    assert scene["title"] == "Studio Name - Sample Scene | Free"
    assert scene["remote_site_id"] == "93788872"
    assert scene["duration"] == 2694
    assert scene["online_media"]["duration_seconds"] == 2694
    assert scene["online_media"]["direct_video_url"].endswith("93788872_2160p.mp4/")
    assert scene["online_media"]["embed_url"] == "https://example.test/embed/93788872"
    assert scene["online_media"]["streams"][0]["kind"] == "direct"
    assert scene["online_media"]["streams"][0]["label"] == "2160p"
    assert scene["online_media"]["streams"][-1]["kind"] == "embed"
    assert scene["studio"]["name"] == "Sample Studio"
    assert [p["name"] for p in scene["performers"]] == ["Person One", "Person Two"]\n    assert "Related Person" not in [p["name"] for p in scene["performers"]]

    source = parse_source_page(
        LIST_HTML,
        "https://example.test/search/sample/relevance/",
        source_name="Example",
        source_slug="example",
        source_url="https://example.test/",
    )

    assert source["source_type"] == "SEARCH"
    assert len(source["scene_candidates"]) == 1
    candidate = source["scene_candidates"][0]
    assert candidate["title"] == "Sample Card Title"
    assert candidate["duration"] == 2672
    assert candidate["studio"]["name"] == "Card Studio"
    assert candidate["performers"][0]["name"] == "Card Person"
    assert candidate["source_preview"]["preview_url"] == "https://preview.example.test/preview/93784844.mp4"

    print(json.dumps({"status": "ok", "scene_title": scene["title"], "source_candidates": len(source["scene_candidates"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

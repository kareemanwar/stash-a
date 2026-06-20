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
<link href="https://www.1porn.tv/videos/deepthroat-foursome-in-sex-class/" rel="canonical"/>
<meta property="og:title" content="Innocent High - Deepthroat Foursome in Sex Class | Free Porn"/>
<meta property="og:image" content="https://img.1porn.tv/93788000/93788872/medium@2x/1.jpg"/>
<meta property="og:description" content="Watch this free porn movie now!"/>
<meta property="video:release_date" content="2024-07-01T18:18:30Z"/>
<meta property="video:duration" content="2694"/>
<meta property="video:tag" content="Blowjob"/>
<script>var pageContext = { videoId: '93788872' };</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"VideoObject","name":"Innocent High - Deepthroat Foursome in Sex Class","duration":"PT0H44M54S","embedUrl":"https://www.1porn.tv/embed/93788872","interactionStatistic":[{"@type":"InteractionCounter","interactionType":"http://schema.org/WatchAction","userInteractionCount":"4875"}]}
</script>
</head>
<body>
<a class="models__item thumb_cs" href="https://www.1porn.tv/sites/innocent-high/"><span>Innocent High</span></a>
<a class="models__item" href="https://www.1porn.tv/models/trinity-olsen/"><span>Trinity Olsen</span></a>
<video>
<source src="https://www.1porn.tv/get_file/93788872_720p.mp4/" type="video/mp4" label="720p">
<source src="https://www.1porn.tv/get_file/93788872_2160p.mp4/" type="video/mp4" label="2160p">
</video>
</body>
</html>
"""

LIST_HTML = """
<html>
<head><link href="https://www.1porn.tv/search/alina-angel/relevance/" rel="canonical"/></head>
<body>
<div class="item">
  <a href="https://www.1porn.tv/videos/foursome-frenzy-in-fishnet/" target="_blank" title="Foursome Frenzy in Fishnet">
    <div class="img thumb__img" data-preview="https://cast.1porn.tv/preview/93784844.mp4">
      <img class="thumb lazyload" data-src="https://img.1porn.tv/93784000/93784844/medium@2x/1.jpg" alt="Foursome Frenzy in Fishnet">
      <span class="duration"> Full Video 44:32 </span>
    </div>
  </a>
  <div class="item-info">
    <a href="https://www.1porn.tv/videos/foursome-frenzy-in-fishnet/" title="Foursome Frenzy in Fishnet">
      <strong class="title"> Foursome Frenzy in Fishnet </strong>
    </a>
    <div class="models">
      <a class="models__item thumb_cs" href="https://www.1porn.tv/sites/team-skeet-x-series/"><span>Team Skeet X Series</span></a>
      <a class="models__item" href="https://www.1porn.tv/models/kenzie-reeves/"><span>Kenzie Reeves</span></a>
    </div>
  </div>
</div>
<div class="pagination"><a href="https://www.1porn.tv/search/alina-angel/relevance/2/">2</a></div>
</body>
</html>
"""


def main() -> None:
    scene = parse_scene_page(
        SCENE_HTML,
        "https://www.1porn.tv/videos/deepthroat-foursome-in-sex-class/",
        source_name="1Porn",
        source_slug="1porn",
        source_url="https://www.1porn.tv/",
    )

    assert scene["title"] == "Innocent High - Deepthroat Foursome in Sex Class"
    assert scene["remote_site_id"] == "93788872"
    assert scene["duration"] == 2694
    assert scene["online_media"]["duration_seconds"] == 2694
    assert scene["online_media"]["direct_video_url"].endswith("93788872_2160p.mp4/")
    assert scene["online_media"]["embed_url"] == "https://www.1porn.tv/embed/93788872"
    assert scene["online_media"]["streams"][0]["kind"] == "direct"
    assert scene["online_media"]["streams"][0]["label"] == "2160p"
    assert scene["online_media"]["streams"][-1]["kind"] == "embed"
    assert scene["studio"]["name"] == "Innocent High"
    assert scene["performers"][0]["name"] == "Trinity Olsen"

    source = parse_source_page(
        LIST_HTML,
        "https://www.1porn.tv/search/alina-angel/relevance/",
        source_name="1Porn",
        source_slug="1porn",
        source_url="https://www.1porn.tv/",
    )

    assert source["source_type"] == "SEARCH"
    assert len(source["scene_candidates"]) == 1
    candidate = source["scene_candidates"][0]
    assert candidate["title"] == "Foursome Frenzy in Fishnet"
    assert candidate["duration"] == 2672
    assert candidate["studio"]["name"] == "Team Skeet X Series"
    assert candidate["performers"][0]["name"] == "Kenzie Reeves"
    assert candidate["source_preview"]["preview_url"] == "https://cast.1porn.tv/preview/93784844.mp4"

    print(json.dumps({"status": "ok", "scene_title": scene["title"], "source_candidates": len(source["scene_candidates"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

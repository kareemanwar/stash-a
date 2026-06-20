# 1Porn scraper implementation

Branch: `feature/1porn-scraper-framework`

## Scope

This implementation adds 1Porn as the first site built with the new small scraper framework approach.

It intentionally keeps the framework minimal:

```text
Fetch -> Page Parse -> Media Resolve -> Output Normalize
```

## Files

- `.local/scrapers/stash-a/_shared/fetch.py`
- `.local/scrapers/stash-a/_shared/text.py`
- `.local/scrapers/stash-a/_shared/urls.py`
- `.local/scrapers/stash-a/_shared/jsonld.py`
- `.local/scrapers/stash-a/_shared/streams.py`
- `.local/scrapers/stash-a/_shared/output.py`
- `.local/scrapers/stash-a/_shared/profiles/kvs.py`
- `.local/scrapers/stash-a/1Porn/1Porn.yml`
- `.local/scrapers/stash-a/1Porn/scraper.py`
- `scripts/dev/test_1porn_scraper_parser.py`

## Behavior

### Scene URL scraping

`1Porn/scraper.py scene-by-url --url <url>` returns native `ScrapedScene` fields:

- `title`
- `details`
- `date`
- `urls`
- `image`
- `studio`
- `performers`
- `tags`
- `remote_site_id`
- `duration`
- typed `online_media`

The KVS profile reads:

- `og:*` metadata.
- `video:*` metadata.
- JSON-LD `VideoObject`.
- `pageContext.videoId`.
- direct `<video>/<source>` MP4 streams.
- stable `/embed/<id>` fallback.
- model links as performers.
- site links as studio.

Direct streams are sorted before embed streams, but the embed fallback is preserved.

### Source/list scraping

`1Porn/scraper.py source-by-url --url <url>` extracts preview scene candidates from KVS-style list cards.

Supported page shapes include:

- home/latest pages
- search pages
- model pages
- network pages
- site pages

Preview candidates include title, URL, thumbnail, preview clip URL in `source_preview`, duration, studio, performers, and remote site id when discoverable. Final scene creation should still hydrate through `scene-by-url` before import.

## Notes

1Porn is a KVS/direct-video-tag site, not an XFileSharing/Streamtape host workflow. Its first media resolver reads direct MP4 `<source>` tags and keeps the JSON-LD embed URL as fallback.

## Checks

Local offline checks run while preparing the implementation:

```bash
python -m py_compile /mnt/data/1porn_impl/_shared/*.py /mnt/data/1porn_impl/_shared/profiles/*.py /mnt/data/1porn_impl/1Porn/scraper.py /mnt/data/1porn_impl/scripts/dev/test_1porn_scraper_parser.py
python /mnt/data/1porn_testrepo/scripts/dev/test_1porn_scraper_parser.py
```

Both passed in the preparation environment.

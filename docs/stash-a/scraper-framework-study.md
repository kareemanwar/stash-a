# Stash-a scraper framework study

Branch: `feature/scraper-framework-study`

Purpose: define a clean, opinionated scraper/extractor architecture before adding more Stash-a scrapers. This is a design/study checkpoint only; no scraper behavior is changed in this commit.

## Sources studied

Project knowledge:

- `docs/stash-a/knowledge-base.md`
- Stash-a online scene notes and verified scraper regressions.

Current Stash/Stash-a contract files:

- `graphql/schema/types/scraper.graphql`
- `graphql/schema/types/scraper_online.graphql`
- `internal/api/resolver_query_scraper.go`

Current Stash-a scraper files sampled:

- `.local/scrapers/stash-a/_shared/online_hosts.py`
- `.local/scrapers/stash-a/Shrmha/Shrmha.py`
- `.local/scrapers/stash-a/Shrmha/ShrmhaOnline.py`
- `.local/scrapers/stash-a/Shrmha/Shrmha.yml`
- `.local/scrapers/stash-a/Nafak/Nafak.py`
- `.local/scrapers/stash-a/T7tAl7zam/T7tAl7zam.py`
- `.local/scrapers/stash-a/T7tAl7zam/T7tAl7zamOnline.py`
- `.local/scrapers/stash-a/T7tAl7zam/T7tAl7zam.yml`
- `.local/scrapers/stash-a/Shraraa/Shraraa.py`

Reference scraper ecosystem:

- `kareemanwar/CommunityScrapers-k/scrapers/Xnxx.yml`

## Contract facts that must not be broken

Stash native scraper schema defines:

- Scrape modes: `NAME`, `FRAGMENT`, `URL`.
- Content types: `SCENE`, `PERFORMER`, `IMAGE`, `GALLERY`, `GROUP`, `MOVIE`.
- `ScrapedScene` native fields include `title`, `code`, `details`, `director`, deprecated `url`, preferred `urls`, `date`, `image`, `studio`, `tags`, `performers`, `groups`, `remote_site_id`, `duration`, and fingerprints.
- `ScrapedScene.image` is documented as a base64 data URL in the upstream GraphQL schema, but existing Stash/community scrapers frequently return remote image URLs. Stash-a currently accepts remote image URLs in tested flows, but the framework should keep image handling explicit.
- Stash-a extends `ScrapedScene` with typed `online_media`.

Stash-a online media scrape extension defines:

- `source_name`: required string.
- `source_slug`: required string.
- `external_id`: optional string.
- `embed_url`: optional stable playback/fallback URL.
- `direct_video_url`: optional direct media URL, often signed/temporary.
- `thumbnail_url`: optional provider thumbnail URL.
- `duration_seconds`: optional int.
- `external_view_count`: optional int.
- `raw_metadata_json`: optional string.
- `streams`: required list of `label`, `kind`, `url`, `position`, `is_primary`.

GraphQL resolver facts:

- `ScrapeSceneURL(ctx, url)` delegates to `scraperCache().ScrapeURL(..., ScrapeContentTypeScene)` and marshals to `models.ScrapedScene`.
- The scraper process boundary remains the Stash scraper system. We should not add side HTTP APIs for website scraping.
- Relationship review/apply stays in native Stash UI. Scrapers provide data; they should not silently overwrite existing user metadata.

## Hard design decisions

### 1. Rewrite the Stash-a scraper layer, not the Stash scraper system

We will build a Stash-a scraper framework inside `.local/scrapers/stash-a/_shared`, but it remains a standard Stash scraper source. YAML files still call scripts. Scripts still write JSON to stdout. GraphQL still receives normal `ScrapedScene` plus Stash-a `online_media`.

Do not build a side app, side DB, local JSON database, browser storage, or REST scraping service.

### 2. Per-site scrapers must become thin adapters

A site scraper should not reimplement:

- URL percent encoding.
- HTTP request headers/charset handling.
- JSON-LD extraction.
- meta/canonical/image extraction.
- `go(...)`/iframe/data-embed discovery.
- stream sorting/deduping.
- direct media probing.
- raw metadata serialization.
- stdout JSON escaping.

A site scraper may define only:

- studio/source constants.
- URL host patterns.
- parser profile choice.
- site-specific selector overrides.
- source/list page selectors when needed.

### 3. Direct media URLs are cache, not identity

For online scenes, the stable identity is the source URL and the stable fallback is the embed/player URL. Direct HLS/MP4 URLs from XFileSharing/Streamtape hosts may be signed and temporary. The framework should publish direct URLs when discovered, but must always preserve embed fallback streams when available.

Player/UI refresh logic may re-scrape direct URLs at playback/hover time, but scraper output must not make direct URLs the only playback path.

### 4. Source/list scrapers must not create final scenes from incomplete metadata

Source page crawlers discover candidates. Scene page scrapers hydrate final metadata. Import utilities can prefilter by native `Scene.urls`, but final creation should use hydrated `scene-by-url` output.

### 5. Generated files are forbidden in scraper commits

No `__pycache__`, `*.pyc`, temporary JSON reports, debug outputs, or local runtime files in commits. `.gitignore` already blocks Python bytecode; future scripts/tests must respect that.

## Proposed module layout

```text
.local/scrapers/stash-a/_shared/
  __init__.py
  cli.py
  contract.py
  http.py
  jsonld.py
  media.py
  site_profiles/
    __init__.py
    generic.py
    wordpress.py
    tubeace.py
  hosts/
    __init__.py
    direct.py
    streamtape.py
    xfilesharing.py
  streams.py
  text.py
  urls.py
```

### `_shared/http.py`

Responsibilities:

- `http_safe_url(url)` for decoded Arabic/non-ASCII URLs.
- `safe_header_url(url)` for Referer/Origin where required.
- `fetch_text(url, headers, timeout)`.
- charset detection.
- common user-agent handling.
- optional retry/backoff hooks.

This module owns the bug class that broke T7t decoded Arabic URLs.

### `_shared/text.py`

Responsibilities:

- `clean_text`.
- HTML label cleanup.
- Arabic/Windows-console-safe JSON stdout.
- whitespace normalization.

### `_shared/urls.py`

Responsibilities:

- `absolute_url`.
- canonical URL extraction helpers.
- source host matching.
- external ID extraction from URL/query/canonical/post id.
- stable scene URL normalization rules.

### `_shared/jsonld.py`

Responsibilities:

- parse JSON-LD scripts.
- flatten `@graph`.
- find `Article`, `WebPage`, `VideoObject`, `ImageObject`.
- safe first/list extraction.

### `_shared/site_profiles/wordpress.py`

Responsibilities:

- WordPress-like title, details, date, thumbnail, tags, view count.
- iframe discovery.
- `go('...')` server selector discovery across buttons, anchors, and generic clickable elements.
- data-embed/href/src player URL discovery with host/path filtering.

### `_shared/site_profiles/tubeace.py`

Responsibilities:

- TubeAce/post-preview source cards.
- pagination `/page/N/` handling.
- source candidate extraction.
- optional candidate hydration handoff.

### `_shared/hosts/xfilesharing.py`

Responsibilities:

- XFileSharing URL/file-code normalization.
- `/e/code`, `/embed-code.html`, `/embed/code`, `/player/code` variants.
- player document fetch.
- `/dl` POST probing.
- packed JavaScript unpacking.
- direct HLS/MP4 extraction.
- duration and quality extraction.
- unavailable markers.

### `_shared/hosts/streamtape.py`

Responsibilities:

- Streamtape `get_video` reconstruction.
- hidden element extraction.
- JavaScript substring reconstruction.
- optional ffprobe validation.
- embed fallback preservation.

### `_shared/hosts/direct.py`

Responsibilities:

- direct `<video>`/`<source>`/JS `file`/`src` extraction.
- HLS quality probe.
- signed URL expiry parsing where possible.

### `_shared/streams.py`

Responsibilities:

- canonical stream dict creation.
- `kind` enum policy: `embed`, `direct` initially.
- position/is_primary reset.
- dedupe by normalized URL.
- direct-before-embed ordering.
- fallback preservation.

### `_shared/contract.py`

Responsibilities:

- normalize `ScrapedScene` payloads.
- normalize `ScrapedSceneOnlineMedia` payloads.
- reject missing required fields early.
- remove internal fields like `page_url`/`canonical_url` before stdout.
- stable `raw_metadata_json` production.
- optional warning collection.

### `_shared/cli.py`

Responsibilities:

- parse Stash scraper CLI/stdin args.
- dispatch operations: `scene-by-url`, future `scene-by-name`, `scene-by-fragment`, source crawl commands.
- consistent exit codes.
- stdout/stderr handling.

## Target per-site scraper shape

A rewritten site scraper should look like this conceptually:

```python
from _shared.runner import SceneByURLScraper
from _shared.site_profiles.wordpress import WordPressSceneProfile

SCRAPER = SceneByURLScraper(
    source_name="تحت الحزام",
    source_slug="t7t-al7zam",
    source_url="https://t7t-al7zam.com/",
    url_hosts=["t7t-al7zam.com"],
    profile=WordPressSceneProfile(...),
    host_extractors=["xfilesharing", "streamtape", "direct"],
)

if __name__ == "__main__":
    SCRAPER.main()
```

The concrete API can change, but the principle is fixed: site files configure and override, shared modules do the heavy lifting.

## Current scraper inventory

### Shrmha

Current status:

- YAML calls `ShrmhaOnline.py scene-by-url`.
- Base scraper is WordPress-like.
- Online wrapper uses shared online host enhancer.
- Known good regression: `https://shrmha.com/?p=306` returns title, thumbnail, embed fallback, direct HLS, duration `87`.
- Streamtape regression: `https://shrmha.com/?p=233` returns duration `429`, direct stream, and fallback.

Framework implications:

- Good candidate for second migration after T7t.
- Should use WordPress profile + XFileSharing/Streamtape host extractors.
- Existing wrapper should disappear after framework migration.

### Nafak

Current status:

- Base scraper is WordPress-like.
- Online wrapper uses shared online host enhancer.
- Source hydrated scraper exists and should remain candidate/hydration oriented.
- Known good regression: `https://nafakarab.com/?p=6878` returns direct streams and duration `145`.

Framework implications:

- Good candidate for third migration.
- Shares most of the Shrmha profile/host behavior.
- Source crawler should be migrated only after scene-by-url is stable.

### T7tAl7zam

Current status:

- YAML calls `T7tAl7zamOnline.py scene-by-url`.
- Base scraper is WordPress-like with Arabic slug URLs.
- Recently fixed decoded Arabic URL handling with `http_safe_url` in base scraper and safe referer handoff in online wrapper.
- Verified decoded Arabic URL returns title, thumbnail, three direct HLS streams, embed fallbacks, duration `345`, and six streams.

Framework implications:

- Best first migration target because the decoded URL bug is verified and easy to protect with tests.
- Must include fixture/test for decoded Arabic URLs.
- Must preserve multiple direct streams plus embed fallbacks.

### Shraraa

Current status:

- Custom script style, already imports `_shared/online_hosts` opportunistically.
- Uses custom URL/HTML helpers and has had host extraction bugs around stream key names and `go(...)` extraction.

Framework implications:

- Migrate after T7t/Shrmha/Nafak.
- Needs careful source/list vs scene-by-url boundary review.
- Should stop using ad-hoc online media dicts and use `contract.py`.

### Arabgy

Current status:

- Included in earlier local patch noise and pycache cleanup.
- Needs inventory before migration.

Framework implications:

- Do not migrate until explicit current-output tests exist.
- Likely use the same WordPress/generic site profile if structure matches.

## Test strategy

### Required test commands

Every scraper framework PR must support these checks:

```bash
python -m py_compile \
  .local/scrapers/stash-a/_shared/*.py \
  .local/scrapers/stash-a/_shared/hosts/*.py \
  .local/scrapers/stash-a/_shared/site_profiles/*.py \
  .local/scrapers/stash-a/*/*.py
```

A real script should replace shell glob fragility:

```bash
python scripts/dev/test_scrapers.py --offline
python scripts/dev/test_scrapers.py --live-smoke
```

### Offline fixtures

Add fixtures under:

```text
.local/scrapers/stash-a/_fixtures/
  T7tAl7zam/
    decoded-arabic-scene.html
    decoded-arabic-scene.expected.json
  Shrmha/
    p306.html
    p306-player.html
    p306.expected.json
  Nafak/
    p6878.html
    p6878.expected.json
```

Offline tests should verify:

- title
- details when available
- date
- image
- urls
- studio
- tags
- remote_site_id
- online_media.source_slug
- online_media.thumbnail_url
- online_media.embed_url
- online_media.duration_seconds
- at least one embed fallback when present
- direct streams only when fixture/probe supports them
- stream ordering and `is_primary`

### Live smoke tests

Live tests can be slower and optional, but current verified URLs should remain smoke tests:

- T7t decoded Arabic URL: `https://t7t-al7zam.com/حفلة-سكس-مصري-رباعي-مزتين-معاهم-دكرين-ي/`
- Shrmha: `https://shrmha.com/?p=306`
- Nafak: `https://nafakarab.com/?p=6878`

Live tests should not be required in normal CI unless explicitly enabled because hosts can expire, throttle, or block.

## Migration plan

### Phase 0: branch and freeze

- Work on `feature/scraper-framework-study` for study/design only.
- Implementation should move to `feature/scraper-framework` after this doc is reviewed.
- Keep `feature/scrapers-sync` stable as the currently verified branch.

### Phase 1: shared foundation, no site migration

Add modules:

- `_shared/http.py`
- `_shared/text.py`
- `_shared/urls.py`
- `_shared/jsonld.py`
- `_shared/streams.py`
- `_shared/contract.py`
- `_shared/hosts/xfilesharing.py`
- `_shared/hosts/streamtape.py`
- `_shared/hosts/direct.py`
- `_shared/site_profiles/wordpress.py`
- `_shared/site_profiles/tubeace.py`
- `_shared/cli.py`

Keep existing scrapers unchanged. Add tests for shared modules first.

### Phase 2: migrate T7t scene-by-url

- Rewrite T7t base/online pair into one thin framework scraper.
- Keep YAML command name stable or provide a compatibility wrapper.
- Preserve output contract exactly for the verified decoded URL.
- Remove duplicated `fetch_html`, JSON-LD, stream builder, and `raw_metadata_json` code from T7t.

### Phase 3: migrate Shrmha and Nafak scene-by-url

- Use the same WordPress profile and host extractors.
- Preserve current regressions: Shrmha p306, Shrmha p233, Nafak p6878.
- Defer source crawler migration until scene-by-url is stable.

### Phase 4: migrate source crawlers

- Define source candidate contract separately from scene scrape contract.
- Source crawlers discover candidates and optional shallow metadata only.
- Hydration must call scene-by-url before final scene creation.

### Phase 5: migrate Shraraa and Arabgy

- Add current-output tests first.
- Migrate only after known samples pass.
- Delete old ad-hoc helpers after parity is proven.

## Delete/merge/rename policy

Allowed after tests prove parity:

- Delete duplicate per-site `fetch_html` implementations.
- Delete duplicate `clean_text`, JSON-LD, stream ordering, and online media builders.
- Merge `*Online.py` wrappers into the framework runner or leave tiny compatibility wrappers only.
- Rename implementation files to `scraper.py` only if YAML is updated and backward compatibility is not needed.

Not allowed:

- Changing the GraphQL schema just to fit scraper refactor.
- Storing scraper outputs in local files as a database.
- Using `custom_fields` for primary metadata.
- Creating side REST endpoints for website extraction.
- Dropping embed fallbacks because direct media was discovered.

## Open questions before implementation

- Should the new site runner expose one canonical file name (`scraper.py`) per site, with old `T7tAl7zamOnline.py` wrappers kept temporarily?
- Should fixture HTML live in `.local/scrapers/stash-a/_fixtures` or `testdata/scrapers`? Keeping it under `.local/scrapers/stash-a/_fixtures` keeps scraper tests self-contained, but `testdata` is more conventional for repo-wide tests.
- Should live smoke tests be opt-in by environment variable, for example `STASHA_LIVE_SCRAPER_TESTS=1`?
- Should `direct_video_url` expiry metadata be included in `raw_metadata_json` so UI refresh can make better decisions without reparsing URLs?

## Recommended next step

Create implementation branch:

```text
feature/scraper-framework
```

First implementation commit should add shared modules and tests only, with no scraper behavior changes. The second commit should migrate T7tAl7zam scene-by-url and prove parity with decoded Arabic URL output.

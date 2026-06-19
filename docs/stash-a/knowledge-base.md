# Stash-a Knowledge Base

This file is the persistent project memory for studied Stash/Stash-a architecture, decisions, repository notes, implementation patterns, and verified findings.

Keep this file concise, factual, and action-oriented. Current code and upstream Stash patterns remain the source of truth.

## Project repositories

### `kareemanwar/stash-a`

- Main clean fork for development.
- Default branch: `develop`.
- New feature work should happen on feature branches, not directly on `develop`.

### `kareemanwar/CommunityScrapers-k`

- Reference for Stash community scraper examples.
- Use for Stash community scraper examples.
- Use for YAML/Python scraper patterns and provider extraction examples.
- Prefer upstream Stash native patterns over community scraper examples when there is a conflict.

### `kareemanwar/CommunityScripts-k`

- Reference for community plugins, themes, userscripts, and utility scripts.
- Useful for understanding plugin/script conventions.
- Do not copy plugin architecture into core Stash unless upstream Stash uses the same native pattern.

### `kareemanwar/plugins-repo-template-k`

- Template/reference for a Stash plugins source index.
- Plugins are placed under a `plugins/` directory and published as an index.
- Use for plugin distribution/index structure only, not core feature architecture.

### `kareemanwar/scrapers-repo-template-k`

- Template/reference for a Stash scrapers source index.
- Scrapers are placed under a `scrapers/` directory and published as an index.
- Use if Stash-a later needs a dedicated scraper source repo.

## Native-first rules

- Reuse Stash models, services, GraphQL/gqlgen patterns, sqlite migrations, scraper architecture, hooks, and React components whenever possible.
- Prefer GraphQL for application data operations.
- Do not add side REST endpoints unless upstream Stash already uses REST for the same kind of operation.
- Use real sqlite migrations. Never create tables at runtime.
- Do not use local JSON files, `.local` files, browser localStorage, or parallel storage as a database.
- Keep changes small and close to upstream. Avoid broad refactors and formatting churn.

## Important Stash facts

- Scene, Performer, Image, and Gallery already have native `urls: [String!]`.
- Old singular `url` fields are deprecated; prefer `urls`.
- Performers, tags, studios, groups, and galleries are native relationships.
- Performer aliases should use native `Performer.alias_list`.
- Scrapers should return/use `ScrapedScene`, `ScrapedPerformer`, `ScrapedImage`, `ScrapedGallery`, and related native scraped models where applicable.

## UI routing and navbar

Studied files:

- `ui/v2.5/src/App.tsx`
- `ui/v2.5/src/components/MainNavbar.tsx`
- `graphql/schema/types/config.graphql`

Findings:

- Main UI pages are lazy-loaded in `App.tsx` and registered in the main React Router `Switch`.
- Existing routes include `/scenes`, `/images`, `/galleries`, `/performers`, `/tags`, `/studios`, `/groups`, `/stats`, and `/settings`.
- The top navbar is defined in `MainNavbar.tsx`.
- Standard top-level menu entries use the menu item array pattern.
- Each menu item has `name`, `message`, `href`, `icon`, `hotkey`, and optional `userCreatable`.
- `configuration.interface.menuItems` can contain an ordered list of standard menu items that should be shown.
- If a new dev-only item is added only to the normal filtered menu list, old saved configs will hide it.
- Developer-only nav items should be appended after filtering the standard configured menu list unless they should become configurable settings.

Implemented pattern:

- The Scraper Test tab is registered as a lazy component in `App.tsx`.
- Its route is `/scraper-test`.
- Its navbar item is appended as a developer menu item after the configured standard menu items.
- This avoids changing saved user menu config and makes the dev tab visible on existing installs.

## Scraper architecture

Studied files:

- `graphql/schema/types/scraper.graphql`
- `internal/api/resolver_query_scraper.go`
- `ui/v2.5/src/components/Scenes/SceneDetails/SceneEditPanel.tsx`
- `ui/v2.5/src/components/Shared/ScraperMenu.tsx`

Findings:

- Scrape modes are `NAME`, `FRAGMENT`, and `URL`.
- Scrape content types include `SCENE`, `PERFORMER`, `IMAGE`, `GALLERY`, and `GROUP`.
- `ScrapedScene` includes native-style fields such as `title`, `urls`, `date`, `image`, `studio`, `tags`, `performers`, `groups`, `remote_site_id`, and `duration`.
- URL scraper resolvers already exist for scenes, performers, galleries, images, and groups.
- Scene edit UI uses existing scraper hooks/services and review/apply dialogs instead of blindly overwriting metadata.
- `ScraperMenu` is the native reusable dropdown for selecting scraper sources in existing UI.

## Community scraper patterns

Example studied:

- `CommunityScrapers-k/scrapers/Xnxx.yml`

Findings:

- Community YAML scrapers can define `sceneByURL`, `sceneByName`, and `sceneByQueryFragment`.
- XPath scraper outputs map website fields into Stash-native scraped fields such as `Title`, `URL`, `Image`, `Date`, `Details`, `Tags`, and `Studio`.
- Website extraction should live in scraper logic, not random app handlers.

## Local scraper development folder

Decision:

- Track `.local/scrapers/**` in git for Stash-a scraper development.
- Continue ignoring all other `.local` runtime state, including config files, databases, logs, generated cache, and downloaded media.

Reasoning:

- `make server-start` runs Stash from `.local`, so the default development scraper path resolves to `.local/scrapers` unless `scrapers_path` is overridden.
- Keeping development scrapers in that folder lets Stash load them natively while allowing GitHub review and iterative edits.
- Only scraper source files should be committed there, such as `.yml`, `.yaml`, `.py`, and shared helper modules needed by those scrapers.

## Scraper Test tab

Goal:

- Add a native-looking `Test` tab at the end of the main navbar.
- Route: `/scraper-test`.
- Purpose: provide a development screen for testing future scraper output.

Initial scope:

- UI infrastructure only.
- Textbox/test input.
- Dropdown menu to choose a scraper/test profile.
- Button to run the selected test action later.
- Output panel for placeholder/raw output.
- No scraper implementation yet.
- No backend, REST endpoint, database write, or side storage.

Implemented files:

- `ui/v2.5/src/components/ScraperTest/ScraperTest.tsx`
- `ui/v2.5/src/App.tsx`
- `ui/v2.5/src/components/MainNavbar.tsx`

Implementation rules:

- Reuse `App.tsx` route pattern.
- Reuse `MainNavbar.tsx` menu item pattern.
- Reuse React Bootstrap/Stash shared component style.
- Keep the first version intentionally small so future scraper work can iterate on it.

## Online scenes

Implemented native storage:

- Online scene provider metadata is stored in native feature tables `scene_online_media` and `scene_online_streams` via sqlite migration `86_scene_online_media.up.sql`.
- Native Scene fields remain the owner for title, date, details, urls, cover image, performers, tags, studio, groups, and galleries.
- Source/page/canonical URLs belong in native `Scene.urls`; do not duplicate them into `scene_online_media`.
- External-only data such as source slug/name, external id, embed URL, direct video URL, remote thumbnail URL, external view count, duration from provider/player metadata, raw provider metadata, and stream list belongs in `scene_online_media` / `scene_online_streams`.
- Do not store online scene metadata in `custom_fields`, browser storage, local JSON, or runtime-created tables.

Implemented UI flow:

- `ScraperTest` can scrape a scene URL, show native review, and create a fileless online scene by creating a native Scene then saving `sceneOnlineMediaSave`.
- `/scenes/new` exposes an `Online` checkbox and `Source URL` field below the title for new scenes.
- When the checkbox is enabled, saving runs the native URL scraper, creates a native Scene from scraped fields plus any user-entered overrides, saves online media/streams, then opens the scene.
- `/scenes/new` checks native `Scene.urls` for the source URL and scraped URLs before creating an online scene. If a matching scene exists, it opens the existing scene instead of creating a duplicate.
- `ScenePlayer` is patched only for fileless scenes with online media. Local-file scenes continue to use the native Stash player.
- Online scene card UI should avoid covering native selection controls; badges belong in card details, while duration overlays should follow the local Scene card overlay pattern.
- Online provider view counts belong in the card text/details area, not on thumbnail overlays.
- Fileless online scene pages expose an `Online` tab next to the native scene tabs. The tab displays `scene_online_media`, `scene_online_streams`, provider view count, duration, native source URL from `Scene.urls`, timestamps, and raw metadata through GraphQL.

## Native Sources

Decision:

- `Source` is a native Stash-a entity for websites, searches, categories, accounts, profiles, channels, collections, and child sources.
- Source parent/child hierarchy is represented by `sources.parent_id`.
- Source URLs live in `source_urls`; media page URLs still belong to native object `urls` fields.
- Source-to-media relationships are many-to-many using `scenes_sources`, `images_sources`, `galleries_sources`, and `groups_sources`.
- Candidate media is stored in dedicated per-type tables (`source_candidate_scenes`, `source_candidate_images`, `source_candidate_galleries`, `source_candidate_groups`, `source_candidate_sources`) so each candidate type can support native-like cards, editable working metadata, promotion, ignore/unignore, and duplicate detection.
- Ignored media is durable in `source_ignored_items`; sync should not reintroduce ignored candidates into the main candidate lists.
- Source sync should upsert candidate records, mark already-stored media by matching native `urls`, and avoid overwriting user-edited candidate working metadata unless explicitly requested.

Initial implementation branch:

- `feature/native-sources` starts from `feature/online-scenes-native`.
- Initial foundation adds migration `88_sources.up.sql`, source/candidate model structs, sqlite store, GraphQL schema/resolver shell, and repository wiring.

## Stash-a scrapers

### Shrmha

- Local development path: `.local/scrapers/stash-a/Shrmha/`.
- First implementation is `sceneByURL` only.
- The scraper returns native `ScrapedScene` fields: title, urls, date, image, details, studio, tags, and remote_site_id when available.
- Shrmha is mapped as a native scraped studio, not as a custom `source_type` field.
- Do not return performers from Shrmha scene pages until a page source has explicit performer data.
- The source page does not expose duration/direct media directly. `ShrmhaOnline.py` probes the embed host, POSTs `/dl`, unpacks the returned JWPlayer script, and extracts `m3u8` direct video URL and `duration_seconds` when available.
- The Shrmha scraper should return `online_media` with embed streams, direct stream when discovered, `duration_seconds`, thumbnail URL, external id, and raw provider metadata. Source page URLs belong only in native `ScrapedScene.urls` / `Scene.urls`.

### Nafak

- Local development path: `.local/scrapers/stash-a/Nafak/`.
- `Nafak.py` implements scene URL scraping for native fields plus online media embed streams.
- `NafakOnline.py` wraps the base scene scraper and mirrors the Shrmha online enhancement path: it probes embed hosts, tries `/dl`, unpacks packed player scripts, extracts direct `mp4`/`m3u8` URLs and duration when available, sorts direct streams by detected HLS height before embed fallbacks, and removes duplicate page/canonical URL fields from online media.
- `NafakSourceHydrated.py` reuses the Shrmha source parser shape for TubeAce-style `post-preview` cards and `/page/N/` pagination, but maps hydrated candidates through the Nafak scene scraper.
- Nafak source pages expose listing metadata; each candidate should be hydrated through `NafakOnline.py scene-by-url` before import.

### Source candidate import utility

- `scripts/dev/import_source_candidate_scenes.py` imports Shrmha/Nafak source candidates one-by-one through GraphQL.
- The utility prints live stderr feedback for each candidate (`CHECK`, `SCRAPE`, `SCRAPED`, `CREATED`, `ONLINE_MEDIA`, `ERROR`).
- After the source preview crawl, the utility prefilters candidates against native `Scene.urls` before invoking `scene-by-url`, so existing scenes do not pay the expensive scene scrape cost.
- The utility still performs a second duplicate check after scene hydration because a scene scraper may add or normalize additional URLs.
- Duplicate safety must use native `Scene.urls` exact matching through `scene_filter.url`, not free-text `q` search.
- The utility is for development imports only; it does not create side storage or bypass native schema.


### Online scene duration sorting

- Scene duration sort/filter should use hybrid local/online duration:
  `COALESCE(video_files.duration, scene_online_media.duration_seconds)`.
- Join only `scene_online_media` for online duration. Do not join `scene_online_streams` in scene list sorting/filtering because it is one-to-many and can duplicate scene rows.
- Verified with GraphQL `findScenes(filter: { sort: "duration", direction: DESC })`; online scenes sorted by `scene_online_media.duration_seconds`.


### Shrmha legacy embed players

- Some Shrmha pages use legacy XFileSharing embed URLs like `/embed-code.html`, for example `shrmharuby.com/embed-tcltzs9kguns.html`.
- ShrmhaOnline should normalize those URLs to the file code, keep the embed as a fallback, and probe the player document for direct HLS/MP4 plus duration.
- Verified with `https://shrmha.com/?p=306`: scraper returned duration 87, direct StreamRuby HLS, and the original iframe fallback.


### Scraped scene online media transport

- `ScrapedScene.online_media` is defined through `graphql/schema/types/scraper_online.graphql` as a native scrape-result extension.
- The GraphQL scrape online types are bound to `pkg/models.ScrapedSceneOnlineMedia` and `pkg/models.ScrapedSceneOnlineStream` in `gqlgen.yml`.
- `models.ScrapedScene` carries transient `OnlineMedia` typed data for scraper review/apply flows; persistent playback data still belongs in `scene_online_media` and `scene_online_streams`.
- Avoid the previous raw JSON/generated resolver bridge for scraped online media; typed model binding is the preferred pattern.
- Verified with `scrapeSceneURL("https://shrmha.com/?p=306")`: GraphQL returned Shrmha online media with duration 87, direct HLS stream, and legacy embed fallback.


### Shared online host extraction

- Online site scrapers should keep site-specific parsing separate from host/player extraction.
- `ShrmhaOnline.py` and `NafakOnline.py` now share XFileSharing-style embed enhancement through `.local/scrapers/stash-a/_shared/online_hosts.py`.
- The shared enhancer owns player document fetching, `/dl` probing, packed JavaScript unpacking, direct MP4/HLS extraction, duration parsing, HLS quality probing, stream ordering, unavailable embed tracking, and removal of internal `page_url`/`canonical_url` fields.
- Site-specific scraper wrappers should call their native `build_online_media` first, then pass the result to the shared enhancer.
- Unknown or unsupported hosts should remain as embed fallback streams instead of being dropped.
- Verified regression checks:
  - Shrmha `https://shrmha.com/?p=306` returns duration `87`, direct HLS, and embed fallback.
  - Nafak `https://nafakarab.com/?p=6878` returns duration `145`, direct streams, and embed fallbacks.
- Streamtape is not handled by this refactor yet; add it as a separate host extractor/change.

### Streamtape direct URL reconstruction

- Streamtape player pages may expose multiple `get_video` candidates through hidden elements and JavaScript `substring(...)` reconstruction.
- The shared Streamtape extractor rejects truncated candidates such as `get_video?id=`.
- Candidate URLs are only published as `direct_video_url` when `ffprobe` can probe them as real media.
- If Streamtape returns JSON/HTML errors for all candidates, keep only the embed fallback and leave `duration_seconds` null.

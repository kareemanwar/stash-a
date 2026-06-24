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

- Stash-a scraper work currently lives under `.local/scrapers/stash-a` so development scrapers can run against local Stash while still being reviewable and versioned.

## Source candidate importer pattern

Studied files:

- `scripts/dev/import_source_candidate_scenes.py`
- `.local/scrapers/stash-a/1Porn/scraper.py`
- `.local/scrapers/stash-a/Arabgy/scraper.py`
- `scripts/dev/import_arabgy_source_candidate_scenes.py`

Findings:

- The source importer is a bulk import helper around scraper scripts. A source scraper exposes `source-by-url` to return lightweight `scene_candidates`, and a scene scraper exposes `scene-by-url` to hydrate one candidate into native-style scene metadata.
- Candidate previews should include native fields where possible: `title`, `urls`, `image`, `date`, `studio`, `performers`, `tags`, `remote_site_id`, and optional `source_preview`.
- Hydrated scenes should map ownership data to native Scene fields and relationships: title/details/date/urls/cover image, studio, performers, tags, and `online_media` for external-only embed/direct/thumbnail/provider metadata.
- `scripts/dev/import_source_candidate_scenes.py` prefilters candidates against existing `Scene.urls` before hydrating scenes, then creates native scenes through GraphQL and saves external playback metadata through `SceneOnlineMedia`.
- Arabgy is a WordPress/TubeAce source, not a KVS source. Its listing cards use `post-preview`/`preview-title`/`wp-post-image`; scene pages use the post iframe as embed media; tags come from `post-page-tags`; performer names are represented by category links under the site’s performer/category area.
- If the main importer cannot be edited directly, a small entrypoint can inject a scraper config into `SCRAPERS` before calling the same importer `main()`; `import_arabgy_source_candidate_scenes.py` follows this pattern for Arabgy.

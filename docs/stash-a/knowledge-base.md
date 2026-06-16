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

Findings:

- Main UI pages are lazy-loaded in `App.tsx` and registered in the main React Router `Switch`.
- Existing routes include `/scenes`, `/images`, `/galleries`, `/performers`, `/tags`, `/studios`, `/groups`, `/stats`, and `/settings`.
- The top navbar is defined in `MainNavbar.tsx`.
- Native top-level menu entries use the `allMenuItems` array.
- Each `allMenuItems` entry has `name`, `message`, `href`, `icon`, `hotkey`, and optional `userCreatable`.
- New top-level tabs should follow this pattern instead of building a custom nav.

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

## Current implementation target: Scraper Test tab

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

Implementation rules:

- Reuse `App.tsx` route pattern.
- Reuse `MainNavbar.tsx` menu item pattern.
- Reuse React Bootstrap/Stash shared component style.
- Keep the first version intentionally small so future scraper work can iterate on it.

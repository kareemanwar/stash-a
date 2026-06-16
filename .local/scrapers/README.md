# Local scraper development

This folder is intentionally tracked for Stash-a scraper development.

`make server-start` runs Stash from `.local`, so the default development scraper path resolves to this folder unless `scrapers_path` is overridden in `.local/config.yml`.

Keep only scraper source files here, such as `.yml`, `.yaml`, `.py`, and shared helper modules needed by those scrapers.

Do not commit local runtime state, databases, logs, downloaded media, credentials, or personal configuration files.

# Scraper online hardening plan

Temporary planning note for hardening online scraper extraction across Stash-a scrapers.

Goals:
- Keep site parsing in scraper code and shared host/player extraction in `_shared/online_hosts.py`.
- Percent-encode non-ASCII URLs before HTTP requests so decoded Arabic URLs from stored scenes can be rescraped.
- Capture generic `go('...')` server links, not only button-specific patterns.
- Normalize online stream contracts to `kind`, `url`, `label`, `position`, `is_primary`.
- Preserve embed fallbacks when direct media cannot be validated.
- Avoid generated cache artifacts in scraper development paths.

This file is a small cloud-side checkpoint before implementation and may be removed or folded into the knowledge base after the scraper hardening commit.

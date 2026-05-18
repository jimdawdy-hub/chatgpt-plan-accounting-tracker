# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-05-17

### Added

- Initial local Flask dashboard for ChatGPT/Codex plan accounting.
- Importer for Codex daily workspace usage JSON reports.
- Importer for Codex daily user/message-count JSON reports.
- Importer for ChatGPT credit usage CSV exports from the admin billing page.
- Automatic report discovery in `~/Downloads` and local `./data`.
- SQLite-backed normalized storage for daily usage, model usage, client usage, credit events, settings, and imported files.
- Selected-plan controls for plan, plan start date, and Business seat count.
- Business plan math using `$25/seat/month` with a 2-seat minimum.
- Net plan value and 30-day projection calculations.
- Direct API dollar-equivalent model breakdown using uncached input, cached input, and output token rates.
- Codex internal credit, purchased-credit, model, client, and plan comparison sections.
- Plain-English explanation of cost buckets and subscription economics.
- In-app instructions for downloading billing credit data and Codex analytics reports.
- Footer attribution, disclaimer, and MIT license notice.

### Notes

- Other-plan comparisons are intentionally conservative because OpenAI does not publish fixed numeric Codex quota caps for every plan.
- This tool is not official billing software and should be treated as an estimate only.

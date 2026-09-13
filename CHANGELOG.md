# Changelog

## 0.1.1 — 2026-09-13

- Brand spelling in the package metadata and docs is now `AlphAI`, the form on
  the logo. Class names are unchanged — they are the published API.

## 0.1.0

Initial release.

- `AlphaAIToolSpec` with four tools, each with a native async twin:
  `search_news`, `get_insider_news`, `get_ticker_sentiment`,
  `get_insider_summary`.
- API key via `ALPHAI_API_KEY` env var or an explicit `api_key=...`.

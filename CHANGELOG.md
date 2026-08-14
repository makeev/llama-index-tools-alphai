# Changelog

## 0.1.0

Initial release.

- `AlphaAIToolSpec` with four tools, each with a native async twin:
  `search_news`, `get_insider_news`, `get_ticker_sentiment`,
  `get_insider_summary`.
- API key via `ALPHAI_API_KEY` env var or an explicit `api_key=...`.

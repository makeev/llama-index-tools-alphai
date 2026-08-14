# llama-index-tools-alphai

LlamaIndex tool spec for [AlphaAI](https://alphai.io) — AI-scored,
ticker-linked financial news and SEC Form 4 insider events, built for AI
agents and trading bots.

Every article on the AlphaAI feed is enriched before you see it: per-ticker
impact analysis, one of 14 categories, and a 1-10 market-relevance score. The
tools here fetch and filter that feed — no scraping, no scoring of your own.

`AlphaAIToolSpec` exposes four tools (each with a native async twin):

- `search_news` — the scored news feed with ticker / category / relevance filters
- `get_insider_news` — SEC Form 4 insider events with a structured who-sold-what block
- `get_ticker_sentiment` — 7-day bullish/neutral/bearish rollup for one ticker
- `get_insider_summary` — 30-day insider buy/sell rollup for one ticker

## Install

```bash
pip install llama-index-tools-alphai
```

Requires Python 3.10+.

## Authentication

Create an API key at [alphai.io/developers](https://alphai.io/developers) — the
free tier works without a card. Export it as `ALPHAI_API_KEY`, or pass
`api_key=...` to the spec.

```bash
export ALPHAI_API_KEY="ak_live_..."
```

## Use in an agent

```python
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.anthropic import Anthropic

from llama_index.tools.alphai import AlphaAIToolSpec

agent = FunctionAgent(
    tools=AlphaAIToolSpec().to_tool_list(),
    llm=Anthropic(model="claude-sonnet-4-5"),
)

response = await agent.run(
    "Are NVDA insiders net buying or selling this month, "
    "and does news sentiment agree with what they're doing?"
)
```

## Use the tools directly

```python
from llama_index.tools.alphai import AlphaAIToolSpec

spec = AlphaAIToolSpec()

docs = spec.search_news(symbol="NVDA", min_relevance=7, max_results=5)
docs[0].text  # title + summary
docs[0].metadata  # tickers, category, relevance_score, url, source, ...

events = spec.get_insider_news(symbol="NVDA", min_relevance=7)
events[0].metadata["insider"]  # side, shares, avg price, total value, 10b5-1 flag

spec.get_ticker_sentiment("NVDA")  # {"bullish": 30, "neutral": 8, "bearish": 4, ...}
spec.get_insider_summary("NVDA")  # 30-day buy/sell counts and dollar values
```

News documents map cleanly into RAG pipelines — `text` is the article title
plus summary, everything else rides in `metadata`.

### Filters

- `symbol` — one ticker (`"NVDA"`; crypto `"BTC-USD"`, foreign listings the
  Yahoo suffix `"VOD.L"`). Share-class siblings are included on the insider
  feed.
- `category` — one of 14: `earnings`, `mergers_acquisitions`, `regulation`,
  `macro_economy`, `sector_analysis`, `market_movers`, `technology`,
  `commodities`, `crypto`, `ipo`, `geopolitics`, `insider`,
  `corporate_actions`, `other`.
- `min_relevance` — 1-10 floor; 7+ keeps only high-signal articles. On the
  insider feed the score is deterministic from the event's dollar value, so it
  works as an "only large trades" dial.
- `max_results` — cap on returned items (1-50).

## Rate limits

Limits are per AlphaAI account, two-layer (per-minute burst + per-day volume):
Free 20/min · 100/day, Basic 60/min · 10,000/day, Pro 150/min · 100,000/day.
The underlying [alphai-sdk](https://pypi.org/project/alphai-sdk/) retries 429s
with backoff automatically.

## Links

- Developer guide: <https://alphai.io/developers>
- API reference: <https://api.alphai.io/api/schema/>
- MCP server (same feed, for MCP-speaking agents): <https://alphai.io/mcp>

AlphaAI output is AI-generated financial information for research, not
investment advice — see [alphai.io/terms](https://alphai.io/terms).

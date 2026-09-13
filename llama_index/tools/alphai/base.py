"""AlphAI tool spec: AI-scored financial news and SEC Form 4 insider events.

Every article on the AlphAI feed already carries an AI enrichment layer
(per-ticker impact analysis, a category, a 1-10 relevance score), so the tools
here do no scoring of their own — they fetch, filter, and map articles into
:class:`llama_index.core.schema.Document` objects with the enrichment exposed
as metadata.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from llama_index.core.schema import Document
from llama_index.core.tools.tool_spec.base import SPEC_FUNCTION_TYPE, BaseToolSpec

from alphai import AsyncClient, Client
from alphai.models import RichNewsArticle

DEFAULT_MAX_RESULTS = 10


def _plain(value: object) -> object:
    """Convert SDK field values into JSON-friendly metadata values."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _enum_str(value: object) -> str:
    return str(getattr(value, "value", value))


def _to_document(article: RichNewsArticle) -> Document:
    original = article.original
    enrichment = article.enrichment
    parts = [original.title.strip(), original.summary.strip()]
    text = "\n\n".join(part for part in parts if part)
    metadata: dict[str, Any] = {
        "uid": original.uid,
        "url": original.url,
        "title": original.title,
        "source": original.source,
        "source_domain": original.source_domain,
        "published_at": _plain(original.time_published),
        "tickers": list(enrichment.tickers),
        "category": _enum_str(enrichment.category),
        "relevance_score": enrichment.relevance_score,
    }
    if article.sources_count is not None:
        metadata["sources_count"] = article.sources_count
    if article.insider is not None:
        event = article.insider
        metadata["insider"] = {
            "side": event.side,
            "transaction_code": event.transaction_code,
            "shares": _plain(event.shares),
            "avg_price_usd": _plain(event.avg_price_usd),
            "total_value_usd": _plain(event.total_value_usd),
            "is_10b5_1": event.is_10b5_1,
            "insider_name": event.insider_name,
            "insider_title": event.insider_title,
            "is_officer": event.is_officer,
            "is_director": event.is_director,
            "is_ten_percent_owner": event.is_ten_percent_owner,
            "transaction_date": _plain(event.transaction_date),
        }
    return Document(text=text, metadata=metadata)


class AlphaAIToolSpec(BaseToolSpec):
    """Tools over the AlphAI financial-news API (https://alphai.io).

    Requires an AlphAI API key (free tier available, no card) — see
    https://alphai.io/developers. The key is read from the ``ALPHAI_API_KEY``
    environment variable unless passed explicitly.

    ```python
    from llama_index.tools.alphai import AlphaAIToolSpec

    tools = AlphaAIToolSpec().to_tool_list()
    ```
    """

    # Typed like the base class (instance-level), not ClassVar — mypy rejects
    # narrowing an inherited instance attribute to a class variable.
    spec_functions: list[SPEC_FUNCTION_TYPE] = [  # noqa: RUF012
        ("search_news", "asearch_news"),
        ("get_insider_news", "aget_insider_news"),
        ("get_ticker_sentiment", "aget_ticker_sentiment"),
        ("get_insider_summary", "aget_insider_summary"),
    ]

    def __init__(self, api_key: str | None = None) -> None:
        """
        Args:
            api_key: AlphAI API key. Defaults to the ``ALPHAI_API_KEY``
                environment variable.
        """
        self._api_key = api_key
        self._client: Client | None = None

    def _sync_client(self) -> Client:
        if self._client is None:
            self._client = Client(api_key=self._api_key)
        return self._client

    def _async_client(self) -> AsyncClient:
        # A fresh client per call: AsyncClient binds to the running event loop,
        # so caching one across calls (and loops) is unsafe.
        return AsyncClient(api_key=self._api_key)

    def search_news(
        self,
        symbol: str | None = None,
        category: str | None = None,
        min_relevance: int | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[Document]:
        """Fetch recent financial news from AlphAI's AI-scored feed, newest first.

        Every article is tagged with tickers, a category, and a 1-10
        market-relevance score. Use it for questions about recent news on a
        stock, a sector, or the market overall.

        Args:
            symbol: Ticker to filter by, e.g. "NVDA". Crypto uses "<SYM>-USD"
                ("BTC-USD"); foreign listings use the Yahoo suffix ("VOD.L").
            category: Category filter. One of: earnings, mergers_acquisitions,
                regulation, macro_economy, sector_analysis, market_movers,
                technology, commodities, crypto, ipo, geopolitics, insider,
                corporate_actions, other.
            min_relevance: Only articles at or above this 1-10 floor; 7 and up
                keeps only high-signal news.
            max_results: Maximum number of articles to return (1-50).
        """
        articles = self._sync_client().news.iter(
            symbol=symbol,
            category=category,
            min_relevance=min_relevance,
            max_items=max_results,
        )
        return [_to_document(article) for article in articles]

    async def asearch_news(
        self,
        symbol: str | None = None,
        category: str | None = None,
        min_relevance: int | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[Document]:
        """Async version of ``search_news``."""
        async with self._async_client() as client:
            return [
                _to_document(article)
                async for article in client.news.iter(
                    symbol=symbol,
                    category=category,
                    min_relevance=min_relevance,
                    max_items=max_results,
                )
            ]

    def get_insider_news(
        self,
        symbol: str | None = None,
        min_relevance: int | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[Document]:
        """Fetch recent SEC Form 4 insider-trading events, newest first.

        Each result is one insider event (a filing's grouped buy/sell
        transactions) with a structured ``insider`` metadata block: side,
        shares, average price, total dollar value, who traded and their role,
        and whether the sale was pre-planned (10b5-1). Use it for questions
        about what executives and directors are buying or selling.

        Args:
            symbol: Ticker to filter by, e.g. "NVDA"; share-class siblings are
                included.
            min_relevance: 1-10 floor. On this feed the score is deterministic
                from the event's dollar value, so a higher floor means larger
                trades only.
            max_results: Maximum number of events to return (1-50).
        """
        articles = self._sync_client().news.insider_iter(
            symbol=symbol,
            min_relevance=min_relevance,
            max_items=max_results,
        )
        return [_to_document(article) for article in articles]

    async def aget_insider_news(
        self,
        symbol: str | None = None,
        min_relevance: int | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[Document]:
        """Async version of ``get_insider_news``."""
        async with self._async_client() as client:
            return [
                _to_document(article)
                async for article in client.news.insider_iter(
                    symbol=symbol,
                    min_relevance=min_relevance,
                    max_items=max_results,
                )
            ]

    def get_ticker_sentiment(self, ticker: str) -> dict[str, Any]:
        """Get a 7-day rollup of AI-assessed news sentiment for one stock.

        Returns how many covered articles were bullish, neutral, or bearish,
        with a per-day breakdown. Use it to gauge how press coverage leans on
        a ticker right now.

        Args:
            ticker: Ticker symbol, e.g. "NVDA".
        """
        return self._sync_client().symbols.sentiment_summary(ticker).model_dump(mode="json")

    async def aget_ticker_sentiment(self, ticker: str) -> dict[str, Any]:
        """Async version of ``get_ticker_sentiment``."""
        async with self._async_client() as client:
            summary = await client.symbols.sentiment_summary(ticker)
        return summary.model_dump(mode="json")

    def get_insider_summary(self, ticker: str) -> dict[str, Any]:
        """Get a 30-day rollup of SEC Form 4 insider activity for one stock.

        Returns buy and sell counts, total dollar values per side, and the
        most active insiders. Use it to answer whether insiders are net buying
        or selling a ticker.

        Args:
            ticker: Ticker symbol, e.g. "NVDA".
        """
        return self._sync_client().symbols.insider_summary(ticker).model_dump(mode="json")

    async def aget_insider_summary(self, ticker: str) -> dict[str, Any]:
        """Async version of ``get_insider_summary``."""
        async with self._async_client() as client:
            summary = await client.symbols.insider_summary(ticker)
        return summary.model_dump(mode="json")

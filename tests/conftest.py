from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from alphai.models.news import (
    EnrichedArticle,
    InsiderEvent,
    OriginalArticle,
    RichNewsArticle,
)
from alphai.models.symbols import TickerInsiderSummary, TickerSentimentSummary


def make_article(
    uid: str = "a1b2c3d4e5f60718",
    title: str = "Nvidia beats on data-center revenue",
    summary: str = "Q2 revenue came in above consensus, driven by data-center demand.",
    tickers: list[str] | None = None,
    relevance_score: int = 8,
    category: str = "earnings",
    insider: InsiderEvent | None = None,
    sources_count: int | None = None,
) -> RichNewsArticle:
    return RichNewsArticle(
        original=OriginalArticle(
            uid=uid,
            title=title,
            url=f"https://example.com/{uid}",
            time_published=datetime(2026, 8, 14, 12, 30, tzinfo=timezone.utc),
            summary=summary,
            source="Example Wire",
            source_domain="example.com",
        ),
        enrichment=EnrichedArticle(
            category=category,
            tickers=tickers if tickers is not None else ["NVDA"],
            relevance_score=relevance_score,
        ),
        insider=insider,
        sources_count=sources_count,
    )


def make_insider_event() -> InsiderEvent:
    return InsiderEvent(
        side="sell",
        transaction_code="S",
        shares=Decimal("120000"),
        avg_price_usd=Decimal("171.31"),
        total_value_usd=Decimal("20557200.00"),
        is_10b5_1=True,
        insider_name="Jensen Huang",
        insider_title="CEO",
        is_officer=True,
        transaction_date=date(2026, 8, 10),
    )


def make_sentiment_summary() -> TickerSentimentSummary:
    return TickerSentimentSummary(ticker="NVDA", days=7, total=42, bullish=30, neutral=8, bearish=4)


def make_insider_summary() -> TickerInsiderSummary:
    return TickerInsiderSummary(
        ticker="NVDA",
        days=30,
        total_transactions=12,
        buy_count=2,
        sell_value_usd=Decimal("20557200.00"),
    )


class FakeNewsResource:
    """Records call kwargs and yields canned articles."""

    def __init__(self, articles: list[RichNewsArticle]) -> None:
        self.articles = articles
        self.iter_calls: list[dict[str, Any]] = []
        self.insider_calls: list[dict[str, Any]] = []

    def iter(self, **kwargs: Any) -> Iterator[RichNewsArticle]:
        self.iter_calls.append(kwargs)
        max_items = kwargs.get("max_items")
        yield from self.articles[:max_items]

    def insider_iter(self, **kwargs: Any) -> Iterator[RichNewsArticle]:
        self.insider_calls.append(kwargs)
        max_items = kwargs.get("max_items")
        yield from self.articles[:max_items]


class FakeSymbolsResource:
    def __init__(self) -> None:
        self.sentiment_calls: list[str] = []
        self.insider_calls: list[str] = []

    def sentiment_summary(self, ticker: str) -> TickerSentimentSummary:
        self.sentiment_calls.append(ticker)
        return make_sentiment_summary()

    def insider_summary(self, ticker: str) -> TickerInsiderSummary:
        self.insider_calls.append(ticker)
        return make_insider_summary()


class FakeClient:
    def __init__(self, articles: list[RichNewsArticle] | None = None) -> None:
        self.news = FakeNewsResource(articles if articles is not None else [])
        self.symbols = FakeSymbolsResource()


class FakeAsyncNewsResource:
    """Async mirror of FakeNewsResource."""

    def __init__(self, articles: list[RichNewsArticle]) -> None:
        self.articles = articles
        self.iter_calls: list[dict[str, Any]] = []
        self.insider_calls: list[dict[str, Any]] = []

    async def iter(self, **kwargs: Any) -> AsyncIterator[RichNewsArticle]:
        self.iter_calls.append(kwargs)
        for article in self.articles[: kwargs.get("max_items")]:
            yield article

    async def insider_iter(self, **kwargs: Any) -> AsyncIterator[RichNewsArticle]:
        self.insider_calls.append(kwargs)
        for article in self.articles[: kwargs.get("max_items")]:
            yield article


class FakeAsyncSymbolsResource:
    async def sentiment_summary(self, ticker: str) -> TickerSentimentSummary:
        return make_sentiment_summary()

    async def insider_summary(self, ticker: str) -> TickerInsiderSummary:
        return make_insider_summary()


class FakeAsyncClient:
    """Async context manager standing in for alphai.AsyncClient."""

    def __init__(self, articles: list[RichNewsArticle] | None = None) -> None:
        self.news = FakeAsyncNewsResource(articles if articles is not None else [])
        self.symbols = FakeAsyncSymbolsResource()

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.fixture()
def articles() -> list[RichNewsArticle]:
    return [make_article(uid=f"uid{i:013d}", title=f"Article {i}") for i in range(25)]

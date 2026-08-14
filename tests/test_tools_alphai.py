from __future__ import annotations

from typing import Any

from alphai.models.news import RichNewsArticle
from llama_index.core.schema import Document
from llama_index.core.tools.tool_spec.base import BaseToolSpec
from llama_index.tools.alphai import AlphaAIToolSpec
from llama_index.tools.alphai.base import _to_document

from conftest import FakeAsyncClient, FakeClient, make_article, make_insider_event


def spec_with(articles: list[RichNewsArticle]) -> tuple[AlphaAIToolSpec, FakeClient]:
    spec = AlphaAIToolSpec(api_key="test")
    fake = FakeClient(articles)
    spec._client = fake  # type: ignore[assignment]
    return spec, fake


def test_class_hierarchy() -> None:
    assert BaseToolSpec in AlphaAIToolSpec.__mro__


def test_spec_functions() -> None:
    assert AlphaAIToolSpec.spec_functions == [
        ("search_news", "asearch_news"),
        ("get_insider_news", "aget_insider_news"),
        ("get_ticker_sentiment", "aget_ticker_sentiment"),
        ("get_insider_summary", "aget_insider_summary"),
    ]


def test_to_tool_list() -> None:
    tools = AlphaAIToolSpec(api_key="test").to_tool_list()
    names = [tool.metadata.name for tool in tools]
    assert names == [
        "search_news",
        "get_insider_news",
        "get_ticker_sentiment",
        "get_insider_summary",
    ]
    descriptions = [tool.metadata.description for tool in tools]
    assert all(description for description in descriptions)
    assert "1-10" in descriptions[0]


def test_document_mapping() -> None:
    document = _to_document(make_article())
    assert isinstance(document, Document)
    assert document.text.startswith("Nvidia beats on data-center revenue")
    assert "above consensus" in document.text
    assert document.metadata["uid"] == "a1b2c3d4e5f60718"
    assert document.metadata["tickers"] == ["NVDA"]
    assert document.metadata["category"] == "earnings"
    assert document.metadata["relevance_score"] == 8
    assert document.metadata["published_at"] == "2026-08-14T12:30:00+00:00"
    assert "insider" not in document.metadata


def test_document_mapping_insider_block() -> None:
    document = _to_document(make_article(insider=make_insider_event()))
    insider = document.metadata["insider"]
    assert insider["side"] == "sell"
    assert insider["shares"] == "120000"
    assert insider["total_value_usd"] == "20557200.00"
    assert insider["is_10b5_1"] is True
    assert insider["insider_name"] == "Jensen Huang"
    assert insider["transaction_date"] == "2026-08-10"


def test_search_news_passes_filters(articles: list[RichNewsArticle]) -> None:
    spec, fake = spec_with(articles)
    documents = spec.search_news(symbol="NVDA", category="earnings", min_relevance=7)
    assert len(documents) == 10
    assert fake.news.iter_calls[0] == {
        "symbol": "NVDA",
        "category": "earnings",
        "min_relevance": 7,
        "max_items": 10,
    }


def test_search_news_max_results(articles: list[RichNewsArticle]) -> None:
    spec, _ = spec_with(articles)
    assert len(spec.search_news(max_results=3)) == 3


def test_get_insider_news_passes_filters(articles: list[RichNewsArticle]) -> None:
    spec, fake = spec_with(articles)
    documents = spec.get_insider_news(symbol="NVDA", min_relevance=8, max_results=2)
    assert len(documents) == 2
    assert fake.news.insider_calls[0] == {
        "symbol": "NVDA",
        "min_relevance": 8,
        "max_items": 2,
    }
    assert not fake.news.iter_calls


def test_get_ticker_sentiment() -> None:
    spec, fake = spec_with([])
    result = spec.get_ticker_sentiment("NVDA")
    assert fake.symbols.sentiment_calls == ["NVDA"]
    assert result["ticker"] == "NVDA"
    assert result["bullish"] == 30


def test_get_insider_summary_decimals_are_json_safe() -> None:
    spec, fake = spec_with([])
    result = spec.get_insider_summary("NVDA")
    assert fake.symbols.insider_calls == ["NVDA"]
    assert result["total_transactions"] == 12
    assert isinstance(result["sell_value_usd"], str)


async def test_asearch_news(articles: list[RichNewsArticle], monkeypatch: Any) -> None:
    spec = AlphaAIToolSpec(api_key="test")
    fake = FakeAsyncClient(articles)
    monkeypatch.setattr(spec, "_async_client", lambda: fake)
    documents = await spec.asearch_news(symbol="NVDA", max_results=4)
    assert len(documents) == 4
    assert fake.news.iter_calls[0]["symbol"] == "NVDA"


async def test_aget_insider_news(articles: list[RichNewsArticle], monkeypatch: Any) -> None:
    spec = AlphaAIToolSpec(api_key="test")
    fake = FakeAsyncClient(articles)
    monkeypatch.setattr(spec, "_async_client", lambda: fake)
    documents = await spec.aget_insider_news(max_results=2)
    assert len(documents) == 2


async def test_aget_ticker_sentiment(monkeypatch: Any) -> None:
    spec = AlphaAIToolSpec(api_key="test")
    monkeypatch.setattr(spec, "_async_client", lambda: FakeAsyncClient([]))
    result = await spec.aget_ticker_sentiment("NVDA")
    assert result["ticker"] == "NVDA"


async def test_aget_insider_summary(monkeypatch: Any) -> None:
    spec = AlphaAIToolSpec(api_key="test")
    monkeypatch.setattr(spec, "_async_client", lambda: FakeAsyncClient([]))
    result = await spec.aget_insider_summary("NVDA")
    assert isinstance(result["sell_value_usd"], str)

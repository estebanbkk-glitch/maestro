"""Tests for TaskAnalyzer (facade), RegexTaskAnalyzer, and LLMTaskAnalyzer."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from maestro.analyzer import TaskAnalyzer, RegexTaskAnalyzer, LLMTaskAnalyzer


# ---------------------------------------------------------------------------
# Original tests — exercise the TaskAnalyzer facade (regex fallback path)
# ---------------------------------------------------------------------------

def test_basic_scraping_task():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Scrape 100 dive shop websites and extract pricing")
    assert task is not None
    assert task.type == "scraping"
    assert task.parameters["count"] == 100
    assert "dive shop" in str(task.parameters.get("domain", "")).lower()
    assert "pricing" in str(task.parameters.get("target", "")).lower()


def test_different_count():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Crawl 50 restaurant sites")
    assert task is not None
    assert task.parameters["count"] == 50


def test_no_count_defaults_to_50():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Scrape hotel websites for pricing")
    assert task is not None
    assert task.parameters["count"] == 50


def test_non_scraping_returns_none():
    analyzer = TaskAnalyzer()
    assert analyzer.analyze("Send an email to john") is None
    assert analyzer.analyze("What's the weather?") is None
    assert analyzer.analyze("") is None


def test_extract_target_keywords():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Scrape 200 sites and extract contact info and pricing")
    assert task is not None
    target = str(task.parameters.get("target", ""))
    assert "contact" in target or "pricing" in target


def test_various_trigger_words():
    analyzer = TaskAnalyzer()
    for verb in ["scrape", "crawl", "extract", "fetch"]:
        task = analyzer.analyze(f"{verb} 30 sites")
        assert task is not None, f"Failed for verb: {verb}"
        assert task.parameters["count"] == 30


# ---------------------------------------------------------------------------
# Analysis task detection tests (regex path)
# ---------------------------------------------------------------------------

def test_analysis_task_detection():
    analyzer = TaskAnalyzer()
    for phrase in [
        "Analyze 1000 rows of customer data for trends",
        "Process 500 records in the sales CSV",
        "Summarize this dataset for patterns",
        "Classify 200 entries in user data",
    ]:
        task = analyzer.analyze(phrase)
        assert task is not None, f"Failed for: {phrase}"
        assert task.type == "analysis"


def test_analysis_extracts_count():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Analyze 1000 rows of customer data")
    assert task is not None
    assert task.parameters["count"] == 1000


def test_analysis_count_defaults():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Analyze customer data for trends")
    assert task is not None
    assert task.parameters["count"] == 1000


def test_analysis_extracts_source():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Analyze 500 rows of customer data for trends")
    assert task is not None
    assert "customer" in str(task.parameters.get("source", "")).lower()


def test_analysis_extracts_type():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Analyze 500 rows of customer data for trends")
    assert task is not None
    assert task.parameters.get("analysis_type") == "trends"


# ---------------------------------------------------------------------------
# API task detection tests (regex path)
# ---------------------------------------------------------------------------

def test_api_task_detection():
    analyzer = TaskAnalyzer()
    for phrase in [
        "Fetch pricing from 20 hotel booking APIs",
        "Call 10 payment endpoints to check status",
        "Query 5 weather API endpoints for data",
        "Hit 15 REST endpoints to get availability",
        "Connect to 8 hotel booking APIs",
    ]:
        task = analyzer.analyze(phrase)
        assert task is not None, f"Failed for: {phrase}"
        assert task.type == "api", f"Expected 'api' for: {phrase}, got: {task.type}"


def test_api_extracts_count():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Fetch pricing from 20 hotel booking APIs")
    assert task is not None
    assert task.parameters["count"] == 20


def test_api_count_defaults():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Fetch data from hotel booking APIs")
    assert task is not None
    assert task.parameters["count"] == 20


def test_api_extracts_source():
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Fetch pricing from 20 hotel booking APIs")
    assert task is not None
    assert "hotel" in str(task.parameters.get("source", "")).lower()


def test_scraping_priority_over_api():
    """When both scraping and API triggers match, scraping wins."""
    analyzer = TaskAnalyzer()
    task = analyzer.analyze("Scrape 50 API documentation websites")
    assert task is not None
    assert task.type == "scraping"


# ---------------------------------------------------------------------------
# LLMTaskAnalyzer unit tests (mocked HTTP)
# ---------------------------------------------------------------------------

def _make_api_response(content_dict: dict) -> bytes:
    """Build a fake DeepSeek JSON response body."""
    return json.dumps({
        "choices": [{
            "message": {"content": json.dumps(content_dict)}
        }]
    }).encode()


def _mock_urlopen(response_bytes: bytes, status: int = 200):
    """Return a context-manager mock for urllib.request.urlopen."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_bytes
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestLLMTaskAnalyzer:
    """Tests for the DeepSeek-backed analyzer with mocked HTTP."""

    def test_available_with_key(self):
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        assert analyzer.available is True

    def test_not_available_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            analyzer = LLMTaskAnalyzer(api_key=None)
            # May still pick up env var from outer env; force empty
            analyzer._api_key = None
            assert analyzer.available is False

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_successful_scraping_parse(self, mock_urlopen_fn):
        mock_urlopen_fn.return_value = _mock_urlopen(
            _make_api_response({
                "type": "scraping",
                "count": 200,
                "domain": "hotel booking",
                "target": "prices",
            })
        )
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        task = analyzer.analyze("grab prices from 200 hotel booking pages")
        assert task is not None
        assert task.type == "scraping"
        assert task.parameters["count"] == 200
        assert task.parameters["domain"] == "hotel booking"
        assert task.parameters["target"] == "prices"

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_successful_analysis_parse(self, mock_urlopen_fn):
        mock_urlopen_fn.return_value = _mock_urlopen(
            _make_api_response({
                "type": "analysis",
                "count": 1000,
                "source": "customer data",
                "analysis_type": "trends",
            })
        )
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        task = analyzer.analyze("analyze 1000 rows of customer data for trends")
        assert task is not None
        assert task.type == "analysis"
        assert task.parameters["count"] == 1000
        assert task.parameters["source"] == "customer data"
        assert task.parameters["analysis_type"] == "trends"

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_successful_api_parse(self, mock_urlopen_fn):
        mock_urlopen_fn.return_value = _mock_urlopen(
            _make_api_response({
                "type": "api",
                "count": 20,
                "source": "hotel booking",
                "target": "pricing",
            })
        )
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        task = analyzer.analyze("fetch pricing from 20 hotel booking APIs")
        assert task is not None
        assert task.type == "api"
        assert task.parameters["count"] == 20
        assert task.parameters["source"] == "hotel booking"
        assert task.parameters["target"] == "pricing"

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_non_scraping_returns_none(self, mock_urlopen_fn):
        mock_urlopen_fn.return_value = _mock_urlopen(
            _make_api_response({"type": None})
        )
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        assert analyzer.analyze("Send an email to john") is None

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_api_error_returns_none(self, mock_urlopen_fn):
        mock_urlopen_fn.side_effect = urllib.error.URLError("connection refused")
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        assert analyzer.analyze("Scrape 100 sites") is None

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_timeout_returns_none(self, mock_urlopen_fn):
        import socket
        mock_urlopen_fn.side_effect = socket.timeout("timed out")
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        assert analyzer.analyze("Scrape 100 sites") is None

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_malformed_json_returns_none(self, mock_urlopen_fn):
        mock_resp = _mock_urlopen(b"not json at all")
        mock_urlopen_fn.return_value = mock_resp
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        assert analyzer.analyze("Scrape 100 sites") is None

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_missing_count_defaults_to_50(self, mock_urlopen_fn):
        mock_urlopen_fn.return_value = _mock_urlopen(
            _make_api_response({
                "type": "scraping",
                "count": None,
                "domain": "restaurants",
                "target": "reviews",
            })
        )
        analyzer = LLMTaskAnalyzer(api_key="sk-test")
        task = analyzer.analyze("collect reviews from restaurants")
        assert task is not None
        assert task.parameters["count"] == 50

    def test_no_key_returns_none_without_calling_api(self):
        analyzer = LLMTaskAnalyzer(api_key=None)
        analyzer._api_key = None  # ensure no env leakage
        assert analyzer.analyze("Scrape 100 sites") is None


# Need the import for URLError in test_api_error_returns_none
import urllib.error


# ---------------------------------------------------------------------------
# Facade fallback tests
# ---------------------------------------------------------------------------

class TestFacadeFallback:
    """Tests that the TaskAnalyzer facade correctly falls back to regex."""

    def test_no_api_key_uses_regex(self):
        analyzer = TaskAnalyzer()
        analyzer._llm._api_key = None  # force no key
        task = analyzer.analyze("Scrape 100 dive shop websites and extract pricing")
        assert task is not None
        assert task.type == "scraping"
        assert task.parameters["count"] == 100

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_api_failure_falls_back_to_regex(self, mock_urlopen_fn):
        mock_urlopen_fn.side_effect = urllib.error.URLError("fail")
        analyzer = TaskAnalyzer()
        analyzer._llm._api_key = "sk-test"  # force LLM path
        task = analyzer.analyze("Scrape 100 dive shop websites and extract pricing")
        assert task is not None
        assert task.type == "scraping"
        assert task.parameters["count"] == 100

    @patch("maestro.analyzer.urllib.request.urlopen")
    def test_llm_none_for_scraping_falls_back(self, mock_urlopen_fn):
        """LLM returns None (non-scraping) but regex recognizes it — facade uses LLM result."""
        mock_urlopen_fn.return_value = _mock_urlopen(
            _make_api_response({"type": None})
        )
        analyzer = TaskAnalyzer()
        analyzer._llm._api_key = "sk-test"
        # LLM says not scraping → facade falls through to regex
        task = analyzer.analyze("Scrape 100 dive shop websites")
        # regex should pick it up
        assert task is not None
        assert task.parameters["count"] == 100


# ---------------------------------------------------------------------------
# Live integration test — only runs when API key is available
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set",
)
def test_live_deepseek_scraping():
    """Integration test: call real DeepSeek API."""
    analyzer = LLMTaskAnalyzer()
    task = analyzer.analyze("Scrape 100 dive shop websites and extract pricing")
    assert task is not None
    assert task.type == "scraping"
    assert task.parameters["count"] == 100

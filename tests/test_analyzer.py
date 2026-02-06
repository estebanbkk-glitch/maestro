"""Tests for TaskAnalyzer."""

from maestro.analyzer import TaskAnalyzer


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

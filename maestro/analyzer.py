"""TaskAnalyzer: parse natural language into structured Task objects."""

from __future__ import annotations

import re

from maestro.models import Task


# Patterns for extracting scraping parameters
_COUNT_PATTERNS = [
    re.compile(r"(\d+)\s+(?:web)?sites?", re.IGNORECASE),
    re.compile(r"(\d+)\s+pages?", re.IGNORECASE),
    re.compile(r"(\d+)\s+urls?", re.IGNORECASE),
    re.compile(r"scrape\s+(\d+)", re.IGNORECASE),
    re.compile(r"crawl\s+(\d+)", re.IGNORECASE),
]

_SCRAPING_TRIGGERS = re.compile(
    r"\b(scrape|scraping|crawl|crawling|extract|fetch|pull\s+data|harvest)\b",
    re.IGNORECASE,
)

# Domain extraction patterns, tried in order
_DOMAIN_PATTERNS = [
    # "100 dive shop websites" — number + noun phrase + sites
    re.compile(r"\b\d+\s+([\w\s]{2,30}?)\s+(?:web)?(?:sites?|pages?)\b", re.IGNORECASE),
    # "hotel websites" — noun phrase + sites (no number)
    re.compile(r"\b([\w][\w\s]{1,30}?)\s+(?:web)?(?:sites?|pages?)\b", re.IGNORECASE),
    # "from dive shops" — from/on/of + noun phrase
    re.compile(r"(?:from|on|of)\s+([\w\s]{2,30}?)(?:\s+and|\s*$|,)", re.IGNORECASE),
]

# What data to extract
_TARGET_PATTERNS = [
    re.compile(r"extract\s+([\w\s,]+?)(?:\s+from|\s+on|\s*$)", re.IGNORECASE),
    re.compile(r"(?:get|pull|scrape)\s+(?:the\s+)?([\w\s,]+?)(?:\s+from|\s+on|\s*$)", re.IGNORECASE),
    re.compile(r"(?:pricing|prices|contacts?|emails?|phone|address|product|review)", re.IGNORECASE),
]


class TaskAnalyzer:
    """Parses user input into a structured Task for the scraping domain."""

    def analyze(self, text: str) -> Task | None:
        """Parse user input into a Task. Returns None if input isn't a scraping task."""
        if not _SCRAPING_TRIGGERS.search(text):
            return None

        parameters: dict[str, object] = {}

        # Extract count
        for pattern in _COUNT_PATTERNS:
            match = pattern.search(text)
            if match:
                parameters["count"] = int(match.group(1))
                break
        if "count" not in parameters:
            parameters["count"] = 50  # sensible default

        # Extract domain/topic
        domain = self._extract_domain(text)
        if domain:
            parameters["domain"] = domain

        # Extract target data
        target = self._extract_target(text)
        if target:
            parameters["target"] = target

        return Task(
            type="scraping",
            description=text.strip(),
            parameters=parameters,
        )

    def _extract_domain(self, text: str) -> str | None:
        """Extract what kind of sites to scrape (e.g., 'dive shops')."""
        for pattern in _DOMAIN_PATTERNS:
            match = pattern.search(text)
            if match:
                domain = match.group(1).strip()
                # Strip leading verbs, numbers, and filler words
                domain = re.sub(
                    r"^(scrape|scraping|crawl|crawling|extract|fetch|pull|the|all|some|every|\d+)\s+",
                    "", domain, flags=re.IGNORECASE,
                )
                # Repeat once more in case of "Scrape 100 ..."
                domain = re.sub(
                    r"^(scrape|scraping|crawl|crawling|extract|fetch|pull|the|all|some|every|\d+)\s+",
                    "", domain, flags=re.IGNORECASE,
                )
                # Skip if it's just a verb or empty after cleanup
                if domain.lower() in ("scrape", "crawl", "extract", "fetch", "pull", "data"):
                    continue
                if domain and len(domain) > 1:
                    return domain
        return None

    def _extract_target(self, text: str) -> str | None:
        """Extract what data to extract (e.g., 'pricing')."""
        # Check for explicit "extract X" pattern first
        match = _TARGET_PATTERNS[0].search(text)
        if match:
            return match.group(1).strip().rstrip(",")

        # Check for standalone target keywords
        keywords = re.findall(
            r"\b(pricing|prices?|contacts?|emails?|phones?|addresses?|products?|reviews?|info|data|details?)\b",
            text,
            re.IGNORECASE,
        )
        if keywords:
            return ", ".join(dict.fromkeys(k.lower() for k in keywords))  # unique, ordered

        return None

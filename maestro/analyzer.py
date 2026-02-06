"""TaskAnalyzer: parse natural language into structured Task objects.

Uses a facade pattern: tries LLM-based analysis (DeepSeek) first,
falls back to regex parsing when the API key is missing or the call fails.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from maestro.models import Task


# ---------------------------------------------------------------------------
# Regex patterns for the fallback analyzer
# ---------------------------------------------------------------------------

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

_ANALYSIS_TRIGGERS = re.compile(
    r"\b(analy[sz]e|analy[sz]ing|process|classify|cluster|predict|summarize|aggregate)\b",
    re.IGNORECASE,
)

_ANALYSIS_DATA_KEYWORDS = re.compile(
    r"\b(data|rows?|records?|csv|json|dataset|table|entries)\b",
    re.IGNORECASE,
)

_ANALYSIS_COUNT_PATTERNS = [
    re.compile(r"(\d+)\s+rows?", re.IGNORECASE),
    re.compile(r"(\d+)\s+records?", re.IGNORECASE),
    re.compile(r"(\d+)\s+entries", re.IGNORECASE),
    re.compile(r"analy[sz]e\s+(\d+)", re.IGNORECASE),
    re.compile(r"process\s+(\d+)", re.IGNORECASE),
]

_ANALYSIS_TYPE_PATTERNS = re.compile(
    r"\b(trends?|anomal(?:y|ies)|patterns?|clusters?|segments?|predictions?|classification|summary|statistics|correlations?)\b",
    re.IGNORECASE,
)

_ANALYSIS_SOURCE_PATTERNS = [
    re.compile(r"(?:of|from)\s+([\w\s]{2,30}?)\s+(?:data|csv|json|records?|rows?)", re.IGNORECASE),
    re.compile(r"([\w]+(?:\s+\w+)?)\s+(?:data|csv|json|dataset)", re.IGNORECASE),
]

_API_TRIGGERS = re.compile(
    r"\b(api|apis|endpoint|endpoints|rest|http|request|requests)\b",
    re.IGNORECASE,
)

_API_ACTION_KEYWORDS = re.compile(
    r"\b(call|fetch|hit|query|poll|invoke|integrate|connect)\b",
    re.IGNORECASE,
)

_API_COUNT_PATTERNS = [
    re.compile(r"(\d+)\s+(?:api|apis|endpoint|endpoints)", re.IGNORECASE),
    re.compile(r"(?:call|fetch|hit|query|poll|invoke)\s+(\d+)", re.IGNORECASE),
    re.compile(r"(\d+)\s+(?:service|services)", re.IGNORECASE),
]

_API_SOURCE_PATTERNS = [
    re.compile(r"(?:from|to)\s+([\w\s]{2,30}?)\s+(?:api|apis|endpoint|endpoints)", re.IGNORECASE),
    re.compile(r"([\w]+(?:\s+\w+)?)\s+(?:api|apis|endpoint|endpoints)", re.IGNORECASE),
]

_API_TARGET_PATTERNS = [
    re.compile(r"(?:fetch|get|extract|pull)\s+([\w\s,]+?)(?:\s+from|\s+via|\s*$)", re.IGNORECASE),
    re.compile(r"(?:pricing|prices?|availability|status|data|inventory|rates?)", re.IGNORECASE),
]

_DOMAIN_PATTERNS = [
    # "100 dive shop websites" — number + noun phrase + sites
    re.compile(r"\b\d+\s+([\w\s]{2,30}?)\s+(?:web)?(?:sites?|pages?)\b", re.IGNORECASE),
    # "hotel websites" — noun phrase + sites (no number)
    re.compile(r"\b([\w][\w\s]{1,30}?)\s+(?:web)?(?:sites?|pages?)\b", re.IGNORECASE),
    # "from dive shops" — from/on/of + noun phrase
    re.compile(r"(?:from|on|of)\s+([\w\s]{2,30}?)(?:\s+and|\s*$|,)", re.IGNORECASE),
]

_TARGET_PATTERNS = [
    re.compile(r"extract\s+([\w\s,]+?)(?:\s+from|\s+on|\s*$)", re.IGNORECASE),
    re.compile(r"(?:get|pull|scrape)\s+(?:the\s+)?([\w\s,]+?)(?:\s+from|\s+on|\s*$)", re.IGNORECASE),
    re.compile(r"(?:pricing|prices|contacts?|emails?|phone|address|product|review)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# RegexTaskAnalyzer — the original regex-based parser
# ---------------------------------------------------------------------------

class RegexTaskAnalyzer:
    """Parses user input into a structured Task using regex heuristics."""

    def analyze(self, text: str) -> Task | None:
        """Parse user input into a Task. Returns None if input isn't recognized."""
        has_api_noun = bool(re.search(r"\b(api|apis|endpoint|endpoints)\b", text, re.IGNORECASE))
        has_scraping = bool(_SCRAPING_TRIGGERS.search(text))
        has_web_target = bool(re.search(r"\b(web)?sites?|pages?\b", text, re.IGNORECASE))

        # API detection: explicit API nouns present, not describing websites
        if has_api_noun and not has_web_target and (
            has_scraping or _API_ACTION_KEYWORDS.search(text)
        ):
            return self._analyze_as_api(text)

        if has_scraping:
            return self._analyze_as_scraping(text)
        if _ANALYSIS_TRIGGERS.search(text) and _ANALYSIS_DATA_KEYWORDS.search(text):
            return self._analyze_as_analysis(text)
        return None

    def _analyze_as_analysis(self, text: str) -> Task:
        """Parse an analysis request into a Task."""
        parameters: dict[str, object] = {}

        # Extract count (rows/records)
        for pattern in _ANALYSIS_COUNT_PATTERNS:
            match = pattern.search(text)
            if match:
                parameters["count"] = int(match.group(1))
                break
        if "count" not in parameters:
            parameters["count"] = 1000  # sensible default for analysis

        # Extract source
        for pattern in _ANALYSIS_SOURCE_PATTERNS:
            match = pattern.search(text)
            if match:
                source = match.group(1).strip()
                # Strip leading verbs/fillers
                source = re.sub(
                    r"^(analy[sz]e|process|classify|the|all|some|\d+)\s+",
                    "", source, flags=re.IGNORECASE,
                )
                if source and len(source) > 1:
                    parameters["source"] = source
                    break

        # Extract analysis type
        type_match = _ANALYSIS_TYPE_PATTERNS.search(text)
        if type_match:
            parameters["analysis_type"] = type_match.group(1).lower()

        return Task(
            type="analysis",
            description=text.strip(),
            parameters=parameters,
        )

    def _analyze_as_api(self, text: str) -> Task:
        """Parse an API integration request into a Task."""
        parameters: dict[str, object] = {}

        # Extract count (endpoints/APIs)
        for pattern in _API_COUNT_PATTERNS:
            match = pattern.search(text)
            if match:
                parameters["count"] = int(match.group(1))
                break
        if "count" not in parameters:
            parameters["count"] = 20  # sensible default for API tasks

        # Extract source (what APIs)
        for pattern in _API_SOURCE_PATTERNS:
            match = pattern.search(text)
            if match:
                source = match.group(1).strip()
                # Strip leading verbs/fillers
                source = re.sub(
                    r"^(call|fetch|hit|query|poll|invoke|the|all|some|\d+)\s+",
                    "", source, flags=re.IGNORECASE,
                )
                if source and len(source) > 1:
                    parameters["source"] = source
                    break

        # Extract target (what data to fetch)
        target_match = _API_TARGET_PATTERNS[0].search(text)
        if target_match:
            parameters["target"] = target_match.group(1).strip().rstrip(",")
        else:
            keywords = re.findall(
                r"\b(pricing|prices?|availability|status|data|inventory|rates?)\b",
                text, re.IGNORECASE,
            )
            if keywords:
                parameters["target"] = ", ".join(dict.fromkeys(k.lower() for k in keywords))

        return Task(
            type="api",
            description=text.strip(),
            parameters=parameters,
        )

    def _analyze_as_scraping(self, text: str) -> Task:
        """Parse a scraping request into a Task."""
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
        match = _TARGET_PATTERNS[0].search(text)
        if match:
            return match.group(1).strip().rstrip(",")

        keywords = re.findall(
            r"\b(pricing|prices?|contacts?|emails?|phones?|addresses?|products?|reviews?|info|data|details?)\b",
            text,
            re.IGNORECASE,
        )
        if keywords:
            return ", ".join(dict.fromkeys(k.lower() for k in keywords))

        return None


# ---------------------------------------------------------------------------
# LLMTaskAnalyzer — DeepSeek-powered parser
# ---------------------------------------------------------------------------

_DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

_SYSTEM_PROMPT = """\
You are a task classifier. Given a user's request, determine if it is a \
web scraping task, a data analysis task, or an API integration task. \
Respond with a JSON object only.

If the request IS a scraping task, respond:
{"type": "scraping", "count": <number of sites/pages, int or null>, \
"domain": <what kind of sites, string or null>, \
"target": <what data to extract, string or null>}

If the request IS a data analysis task, respond:
{"type": "analysis", "count": <number of rows/records, int or null>, \
"source": <what data to analyze, string or null>, \
"analysis_type": <what to find, string or null>}

If the request IS an API integration task, respond:
{"type": "api", "count": <number of endpoints/APIs, int or null>, \
"source": <what APIs to call, string or null>, \
"target": <what data to fetch, string or null>}

If the request is NEITHER, respond:
{"type": null}

Rules:
- count should be an integer if mentioned, otherwise null
- For scraping: domain is a short noun phrase (e.g. "dive shops"), target is what to extract
- For analysis: source is the data being analyzed (e.g. "customer data"), analysis_type is the goal (e.g. "trends")
- For api: source is what kind of APIs (e.g. "hotel booking"), target is what data to fetch (e.g. "pricing")
- Respond with JSON only, no explanation"""


class LLMTaskAnalyzer:
    """Parses user input into a structured Task using the DeepSeek API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")

    @property
    def available(self) -> bool:
        """True when an API key is configured."""
        return bool(self._api_key)

    def analyze(self, text: str) -> Task | None:
        """Call DeepSeek to classify and parse the task.

        Returns a Task for recognized requests, None otherwise.
        Returns None on any error (caller should fall back to regex).
        """
        if not self.available:
            return None

        try:
            return self._call_api(text)
        except Exception:  # noqa: BLE001 — intentional broad catch for facade fallback
            return None

    def _call_api(self, text: str) -> Task | None:
        """Make the actual HTTP request to DeepSeek."""
        payload = json.dumps({
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }).encode()

        req = urllib.request.Request(
            _DEEPSEEK_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())

        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        task_type = parsed.get("type")
        if task_type not in ("scraping", "analysis", "api"):
            return None

        parameters: dict[str, object] = {}
        if parsed.get("count") is not None:
            parameters["count"] = int(parsed["count"])
        else:
            defaults = {"scraping": 50, "analysis": 1000, "api": 20}
            parameters["count"] = defaults.get(task_type, 50)

        if task_type == "scraping":
            if parsed.get("domain"):
                parameters["domain"] = str(parsed["domain"])
            if parsed.get("target"):
                parameters["target"] = str(parsed["target"])
        elif task_type == "api":
            if parsed.get("source"):
                parameters["source"] = str(parsed["source"])
            if parsed.get("target"):
                parameters["target"] = str(parsed["target"])
        else:
            if parsed.get("source"):
                parameters["source"] = str(parsed["source"])
            if parsed.get("analysis_type"):
                parameters["analysis_type"] = str(parsed["analysis_type"])

        return Task(
            type=task_type,
            description=text.strip(),
            parameters=parameters,
        )


# ---------------------------------------------------------------------------
# TaskAnalyzer — public facade
# ---------------------------------------------------------------------------

class TaskAnalyzer:
    """Facade: tries LLM analysis first, falls back to regex.

    Without a DEEPSEEK_API_KEY environment variable, behaves identically
    to the original regex-only implementation.
    """

    def __init__(self) -> None:
        self._llm = LLMTaskAnalyzer()
        self._regex = RegexTaskAnalyzer()

    @property
    def llm_available(self) -> bool:
        """True when the LLM analyzer has an API key configured."""
        return self._llm.available

    def analyze(self, text: str) -> Task | None:
        """Parse user input into a Task. Returns None if input isn't recognized."""
        if self._llm.available:
            result = self._llm.analyze(text)
            if result is not None:
                return result
        return self._regex.analyze(text)

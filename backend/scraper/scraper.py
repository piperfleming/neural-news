#!/usr/bin/env python3
"""
Daily scraper: runs "Artificial intelligence" + each topic category search
using news-only search, collects top 10 article URLs per query, deduplicates,
and ingests them into the backend via POST /api/articles/ingest. No changes
to tagging or summarization — the backend handles extraction and LLM analysis.

Topic categories match backend VALID_TAGS: Research, Policy, Models, Companies,
Hardware & Infrastructure, Security & Misuse.

Usage (from backend folder):
  python scraper/scraper.py              # run once, ingest to BACKEND_URL
  python scraper/scraper.py --dry-run    # only print URLs, do not ingest
  python scraper/scraper.py --schedule   # run once every 24 hours

Environment: BACKEND_URL (default http://localhost:8000).
Start the backend first and make sure dependencies are installed in virtualenv.
"""

import argparse
import logging
import os
import sys
import time
from urllib.parse import urlparse

import requests 
from ddgs import DDGS

# Topic categories aligned with backend app.services.llm_service.VALID_TAGS
# Search query = "Artificial intelligence" + topic (e.g. "Artificial intelligence research")
TOPIC_CATEGORIES = [
    "Research",
    "Policy",
    "Models",
    "Companies",
    "Hardware and Infrastructure",
    "Security and Misuse",
]

BASE_QUERY = "Artificial intelligence"
MAX_RESULTS_PER_QUERY = 10
DEFAULT_BACKEND_URL = "http://localhost:8000"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication: strip fragment, lowercase, strip trailing slash."""
    try:
        parsed = urlparse(url)
        # Rebuild without fragment; optional: normalize scheme and netloc to lower
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += "?" + parsed.query
        return normalized.rstrip("/") or normalized
    except Exception:
        return url


def search_top_urls(query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> list[str]:
    """Return list of news article URLs for the given query (up to max_results). Uses news search only."""
    urls = []
    try:
        ddgs = DDGS()
        results = ddgs.news(query, max_results=max_results)
        if results is None:
            return urls
        for r in (results if isinstance(results, list) else list(results)):
            href = r.get("url") or r.get("href") or r.get("link")
            if href and href.startswith("http"):
                urls.append(href)
    except Exception as e:
        logger.warning("Search failed for %r: %s", query, e)
    return urls


def collect_all_urls() -> set[str]:
    """Run all topic searches and return a deduplicated set of URLs."""
    seen = set()
    for topic in TOPIC_CATEGORIES:
        query = f"{BASE_QUERY} {topic.lower()}"
        logger.info("Searching: %s", query)
        urls = search_top_urls(query)
        for url in urls:
            key = normalize_url(url)
            if key not in seen:
                seen.add(key)
        logger.info("  -> %d new URLs (total unique so far: %d)", len(urls), len(seen))
    return seen


def ingest_url(backend_url: str, url: str) -> bool:
    """
    POST url to backend ingest. Returns True if ingested (201), False if duplicate (409)
    or other non-success. Raises on connection errors if you want to retry.
    """
    ingest_url_endpoint = f"{backend_url.rstrip('/')}/api/articles/ingest"
    try:
        resp = requests.post(
            ingest_url_endpoint,
            json={"url": url},
            timeout=60,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code == 201:
            logger.info("Ingested: %s", url[:80] + ("..." if len(url) > 80 else ""))
            return True
        if resp.status_code == 409:
            logger.debug("Already exists (409): %s", url[:60])
            return False
        logger.warning("Ingest %s -> %s: %s", resp.status_code, url[:60], resp.text[:200])
        return False
    except requests.RequestException as e:
        logger.warning("Request failed for %s: %s", url[:60], e)
        return False


def run(dry_run: bool, backend_url: str) -> None:
    """Collect URLs and optionally ingest them."""
    all_urls = collect_all_urls()
    logger.info("Total unique URLs: %d", len(all_urls))

    if dry_run:
        for u in sorted(all_urls):
            print(u)
        return

    ingested = 0
    for url in all_urls:
        if ingest_url(backend_url, url):
            ingested += 1
    logger.info("Ingested %d new articles (%d duplicates/invalid URLs skipped)", ingested, len(all_urls) - ingested)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search AI + topic categories, collect top 10 URLs per query, ingest into backend."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only run searches and print URLs; do not call backend ingest",
    )
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("BACKEND_URL", DEFAULT_BACKEND_URL),
        help="Backend base URL (default: env BACKEND_URL or http://localhost:8000)",
    )
    args = parser.parse_args()
    
    run(args.dry_run, args.backend_url)


if __name__ == "__main__":
    main()
    sys.exit(0)

"""Extract article content from a URL using trafilatura."""
from dataclasses import dataclass

import trafilatura


@dataclass
class ExtractedArticle:
    """Structured result of article extraction."""

    title: str
    text: str
    author: str | None
    date: str | None
    source: str | None  # site name


def extract_article(url: str) -> ExtractedArticle:
    """Fetch a URL and extract article text + metadata.

    trafilatura handles:
    - HTTP fetching
    - Boilerplate removal (nav, ads, footers)
    - Encoding detection
    - Metadata extraction (title, author, date, sitename)

    Raises:
        ValueError: If the URL cannot be fetched or content cannot be extracted.
    """
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"Could not fetch URL: {url}")

    metadata = trafilatura.extract_metadata(downloaded)

    text = trafilatura.extract(downloaded)
    if not text:
        raise ValueError(f"Could not extract article content from: {url}")

    return ExtractedArticle(
        title=metadata.title if metadata and metadata.title else "Untitled",
        text=text,
        author=metadata.author if metadata else None,
        date=metadata.date if metadata else None,
        source=metadata.sitename if metadata else None,
    )

import asyncio
import logging
from typing import List

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

from utils.helpers import clean_text

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = 5) -> List[dict]:
    """Search DuckDuckGo and return list of {url, title, snippet}. Runs sync (DDGS has no async API)."""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results, region="wt-wt"):
                results.append({
                    "url": r.get("href", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                })
        return results
    except Exception as e:
        logger.warning("DuckDuckGo search failed for query '%s': %s", query, e)
        return []


async def scrape_url(client: httpx.AsyncClient, url: str) -> str:
    """Async-scrape a single URL using a shared AsyncClient. Returns cleaned text (max 1500 words)."""
    if not url:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
        response = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        content = None
        for selector in ["main", "article", "body"]:
            content = soup.find(selector)
            if content:
                break

        if not content:
            return ""

        text = content.get_text(separator=" ", strip=True)
        return clean_text(text, max_words=1500)
    except Exception as e:
        logger.debug("Scrape failed for %s: %s", url, e)
        return ""


async def search_and_scrape(sub_questions: List[str], max_sources: int = 10) -> List[dict]:
    """Search all sub-questions concurrently, then scrape all candidate URLs concurrently."""

    # Step 1: Run all DuckDuckGo searches concurrently (each in its own thread — DDGS is sync)
    search_results_per_q: List[List[dict]] = await asyncio.gather(
        *[asyncio.to_thread(search_web, q, 5) for q in sub_questions]
    )

    # Deduplicate URLs while preserving order
    seen_urls: set = set()
    candidates: List[dict] = []
    for results in search_results_per_q:
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                candidates.append(r)

    # Fetch up to max_sources * 2 candidates so we have spares after filtering empties
    to_fetch = candidates[: max_sources * 2]

    # Step 2: Scrape all candidate URLs concurrently with a single shared AsyncClient
    async with httpx.AsyncClient() as client:
        contents: List[str] = await asyncio.gather(
            *[scrape_url(client, r["url"]) for r in to_fetch]
        )

    # Build final list — keep only non-empty, stop at max_sources
    all_results: List[dict] = []
    for r, content in zip(to_fetch, contents):
        if not content:
            continue
        all_results.append({
            "url": r["url"],
            "title": r.get("title", ""),
            "content": content,
        })
        if len(all_results) >= max_sources:
            break

    return all_results

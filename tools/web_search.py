import time
from typing import List

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

from utils.helpers import clean_text


def search_web(query: str, max_results: int = 5) -> List[dict]:
    """Search DuckDuckGo and return list of {url, title, snippet}."""
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
    except Exception:
        return []


def scrape_url(url: str) -> str:
    """Scrape a URL and return cleaned text content (max 1500 words)."""
    if not url:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noisy tags
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        # Try to find the most content-rich element
        content = None
        for selector in ["main", "article", "body"]:
            content = soup.find(selector)
            if content:
                break

        if not content:
            return ""

        text = content.get_text(separator=" ", strip=True)
        return clean_text(text, max_words=1500)
    except Exception:
        return ""


def search_and_scrape(sub_questions: List[str], max_sources: int = 10) -> List[dict]:
    """Search and scrape for each sub-question, returning combined unique sources."""
    seen_urls = set()
    all_results = []

    for question in sub_questions:
        if len(all_results) >= max_sources:
            break

        search_results = search_web(question, max_results=5)

        for result in search_results:
            if len(all_results) >= max_sources:
                break

            url = result.get("url", "")
            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            time.sleep(1)  # polite scraping delay
            content = scrape_url(url)

            if not content:
                continue

            all_results.append({
                "url": url,
                "title": result.get("title", ""),
                "content": content,
            })

    return all_results

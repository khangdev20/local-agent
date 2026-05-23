"""
Web search via DuckDuckGo — không cần API key.
Dùng httpx để fetch HTML và parse kết quả.
"""
from __future__ import annotations

import re
import urllib.parse

import httpx


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept-Language": "en-US,en;q=0.9",
}


async def web_search(query: str, max_results: int = 5) -> str:
    """
    Search DuckDuckGo and return top results as text.
    No API key required — uses the HTML endpoint.
    """
    encoded = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
    except httpx.TimeoutException:
        return "Error: Search request timed out."
    except httpx.HTTPError as e:
        return f"Error: HTTP error during search: {e}"

    html = resp.text
    results = _parse_ddg_html(html, max_results)

    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   URL: {r['url']}")
        lines.append(f"   {r['snippet']}\n")

    return "\n".join(lines)


def _parse_ddg_html(html: str, max_results: int) -> list[dict]:
    """Extract results from DuckDuckGo HTML response."""
    results = []

    # Find result blocks
    blocks = re.findall(
        r'<div class="result__body">(.*?)</div>\s*</div>',
        html,
        re.DOTALL,
    )

    for block in blocks[:max_results]:
        # Title
        title_match = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, re.DOTALL)
        title = _strip_tags(title_match.group(1)) if title_match else "No title"

        # URL
        url_match = re.search(r'href="([^"]+)"', block)
        url = url_match.group(1) if url_match else ""
        # DDG uses redirect URLs — extract real URL
        if "uddg=" in url:
            real = re.search(r"uddg=([^&]+)", url)
            if real:
                url = urllib.parse.unquote(real.group(1))

        # Snippet
        snippet_match = re.search(r'class="result__snippet">(.*?)</a>', block, re.DOTALL)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""

        if title and url:
            results.append({"title": title.strip(), "url": url, "snippet": snippet.strip()})

    return results


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()

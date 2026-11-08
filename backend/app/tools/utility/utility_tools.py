import math
import re
import urllib.parse
import base64
from datetime import datetime
from typing import Dict, Any, List
import httpx
from bs4 import BeautifulSoup

from backend.app.tools.base import BaseTool, ToolParameter
from backend.app.tools.registry import tool_registry
from backend.app.database.repositories.memory_repo import MemoryRepository

tool_web_search = BaseTool(
    name="web_search",
    description="Searches the live internet using the local machine network and returns search results with titles, snippets, and URLs. Use this whenever the user asks to search the web, check current news, look up documentation, or find online information.",
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="query", type="string", description="The search query keywords in English or Persian"),
        ToolParameter(name="max_results", type="integer", description="Maximum number of results to return (default: 8)", required=False, default=8)
    ]
)

tool_fetch_web_page = BaseTool(
    name="fetch_web_page",
    description="Fetches and extracts clean, readable text content from a specific web page URL. Use this to read documentation, articles, or specific search results.",
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="url", type="string", description="The full HTTP/HTTPS URL of the web page to read")
    ]
)

tool_datetime = BaseTool(
    name="get_current_datetime",
    description="Returns current local date, time, day of the week, and ISO-8601 timestamp.",
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[]
)

tool_calculate = BaseTool(
    name="calculate",
    description="Evaluates a mathematical expression safely using python math operators.",
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="expression", type="string", description="The mathematical expression (e.g. '2 ** 10', 'sqrt(144) + 5')")
    ]
)

tool_search_history = BaseTool(
    name="search_conversation_history",
    description="Searches all historical conversation messages using full-text search (SQLite FTS5).",
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="query", type="string", description="Search query keywords or phrase"),
        ToolParameter(name="limit", type="integer", description="Maximum results (default 10)", required=False, default=10)
    ]
)

tool_get_memory = BaseTool(
    name="retrieve_relevant_memory",
    description="Retrieves saved persistent facts, user preferences, and project guidelines from memory.",
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="category", type="string", description="Optional category: 'user_preference', 'project_detail', 'environment'", required=False),
        ToolParameter(name="query", type="string", description="Optional keyword search query", required=False)
    ]
)

tool_save_memory = BaseTool(
    name="save_conversation_memory",
    description="Persists an important fact, preference, or project insight into long-term memory.",
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="content", type="string", description="The fact or insight to remember"),
        ToolParameter(name="category", type="string", description="Category: 'user_preference', 'project_detail', 'environment', 'instruction'", required=False, default="project_detail")
    ]
)

# --- Handlers ---

async def handle_datetime(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now()
    return {
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "timestamp_unix": int(now.timestamp())
    }

async def handle_calculate(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    expr = args.get("expression", "")
    safe_dict = {
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        "pow": pow, "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "log": math.log, "log10": math.log10, "pi": math.pi, "e": math.e
    }
    try:
        # Evaluate safely restricted to math names and no builtins
        res = eval(expr, {"__builtins__": {}}, safe_dict)
        return {"expression": expr, "result": res}
    except Exception as e:
        return {"error": f"Evaluation error: {str(e)}"}

async def handle_search_history(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    limit = args.get("limit", 10)
    matches = await MemoryRepository.search_messages_fts(query, limit)
    return {"query": query, "count": len(matches), "matches": matches}

async def handle_get_memory(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    category = args.get("category")
    if query:
        facts = await MemoryRepository.search_facts(query, limit=15)
    else:
        facts = await MemoryRepository.list_facts(category, limit=20)
    return {"facts": facts, "count": len(facts)}

async def handle_save_memory(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    content = args.get("content", "")
    category = args.get("category", "project_detail")
    conv_id = ctx.get("conversation_id")
    fact = await MemoryRepository.save_fact(
        conversation_id=conv_id,
        category=category,
        content=content,
        confidence=1.0
    )
    return {"status": "saved", "fact": fact}

def decode_bing_url(bing_url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(bing_url)
        qs = urllib.parse.parse_qs(parsed.query)
        u_val = qs.get("u", [""])[0]
        if u_val.startswith("a1"):
            b64_str = u_val[2:]
            b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
            return base64.urlsafe_b64decode(b64_str).decode("utf-8", errors="ignore")
    except Exception:
        pass
    return bing_url

def expand_search_queries(raw_query: str) -> List[str]:
    queries = [raw_query.strip()]
    lower = raw_query.lower()
    # Expand queries for movie / release lookups if requested
    if "movie" in lower or "film" in lower:
        year_match = re.search(r"\b(20\d\d)\b", raw_query)
        year = year_match.group(1) if year_match else "2026"
        if "imdb" in lower and not "site:imdb.com" in lower:
            queries.append(f"{year} latest release movies site:imdb.com")
    return queries

async def handle_web_search(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    raw_query = args.get("query", "").strip()
    max_results = int(args.get("max_results") or 8)
    if not raw_query:
        return {"error": "Query parameter is required"}

    queries_to_try = expand_search_queries(raw_query)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
    }

    last_error = None

    # Strategy 1: DuckDuckGo Search (HTML / Lite) - Priority Engine
    for q in queries_to_try:
        for trust_env in [True, False]:
            try:
                timeout_cfg = httpx.Timeout(8.0, connect=4.0)
                async with httpx.AsyncClient(timeout=timeout_cfg, trust_env=trust_env, follow_redirects=True) as client:
                    resp = await client.get("https://html.duckduckgo.com/html/", params={"q": q}, headers=headers)
                    if resp.status_code == 200 and "challenge" not in resp.text.lower() and "anomaly.js" not in resp.text.lower():
                        soup = BeautifulSoup(resp.text, "html.parser")
                        results = []
                        for res in soup.select(".result"):
                            title_el = res.select_one(".result__title a")
                            snippet_el = res.select_one(".result__snippet")
                            if title_el:
                                raw_url = title_el.get("href", "")
                                clean_url = raw_url
                                if "uddg=" in raw_url:
                                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                                    clean_url = parsed.get("uddg", [raw_url])[0]
                                results.append({
                                    "title": title_el.get_text(strip=True),
                                    "url": clean_url,
                                    "snippet": snippet_el.get_text(strip=True) if snippet_el else ""
                                })
                                if len(results) >= max_results:
                                    break
                        if results:
                            return {
                                "query": raw_query,
                                "count": len(results),
                                "results": results,
                                "source": "duckduckgo"
                            }
            except Exception as e:
                err_str = str(e) or type(e).__name__
                last_error = f"DuckDuckGo (trust_env={trust_env}): {err_str}"

    # Strategy 2: Bing Search (Fast, robust, decodes URLs, supports dual queries)
    collected_results = []
    seen_urls = set()

    for q in queries_to_try:
        for trust_env in [True, False]:
            try:
                timeout_cfg = httpx.Timeout(12.0, connect=6.0)
                async with httpx.AsyncClient(timeout=timeout_cfg, trust_env=trust_env, follow_redirects=True) as client:
                    bing_url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&setlang=en"
                    resp = await client.get(bing_url, headers=headers)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for h2 in soup.find_all("h2"):
                            a = h2.find("a")
                            if not a:
                                continue
                            title = a.get_text(strip=True)
                            raw_url = a.get("href", "")
                            if not raw_url.startswith("http") or "go.microsoft.com" in raw_url:
                                continue
                            clean_url = decode_bing_url(raw_url)
                            if clean_url in seen_urls:
                                continue
                            seen_urls.add(clean_url)
                            parent = h2.find_parent("li") or h2.parent
                            snippet = ""
                            if parent:
                                p = parent.find("p")
                                if p:
                                    snippet = p.get_text(strip=True)
                            collected_results.append({
                                "title": title,
                                "url": clean_url,
                                "snippet": snippet
                            })
                            if len(collected_results) >= max_results:
                                break
                    if collected_results:
                        break
            except Exception as e:
                err_str = str(e) or type(e).__name__
                last_error = f"Bing (trust_env={trust_env}): {err_str}"
        if len(collected_results) >= max_results:
            break

    if collected_results:
        return {
            "query": raw_query,
            "count": len(collected_results),
            "results": collected_results,
            "source": "bing"
        }

    # Strategy 3: Wikipedia Search API fallback
    try:
        wiki_headers = {"User-Agent": "NOVA-Agent/2.0 (https://nova.ai; contact@nova.ai)"}
        for q in queries_to_try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=True, follow_redirects=True) as client:
                wiki_api = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(q)}&limit={max_results}&format=json"
                resp = await client.get(wiki_api, headers=wiki_headers)
                if resp.status_code == 200:
                    data = resp.json()
                    titles = data[1] if len(data) > 1 else []
                    snippets = data[2] if len(data) > 2 else []
                    urls = data[3] if len(data) > 3 else []
                    results = []
                    for i in range(min(len(titles), len(urls))):
                        results.append({
                            "title": titles[i],
                            "url": urls[i],
                            "snippet": snippets[i] if i < len(snippets) else ""
                        })
                    if results:
                        return {
                            "query": raw_query,
                            "count": len(results),
                            "results": results,
                            "source": "wikipedia"
                        }
    except Exception as e:
        err_str = str(e) or type(e).__name__
        last_error = f"Wiki: {err_str}"

    return {
        "error": f"Web search could not retrieve results. Last engine detail: {last_error or 'No response from search backends'}",
        "query": raw_query,
        "results": []
    }

async def handle_fetch_web_page(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url", "").strip()
    if not url:
        return {"error": "URL parameter is required"}

    # Special optimized path for Wikipedia pages to completely avoid 403 blocks
    if "wikipedia.org/wiki/" in url:
        try:
            wiki_slug = url.split("wikipedia.org/wiki/")[1].split("#")[0].split("?")[0].strip()
            if wiki_slug:
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_slug}"
                async with httpx.AsyncClient(timeout=10.0, trust_env=True, follow_redirects=True) as client:
                    resp = await client.get(summary_url, headers={"User-Agent": "NOVAResearch/1.0 (contact@nova.ai)"})
                    if resp.status_code == 200:
                        data = resp.json()
                        title = data.get("title", wiki_slug)
                        extract = data.get("extract", "")
                        desc = data.get("description", "")
                        content = f"{title}\n{desc}\n\n{extract}" if desc else f"{title}\n\n{extract}"
                        return {
                            "url": url,
                            "title": title,
                            "content": content,
                            "character_count": len(content),
                            "truncated": False,
                            "source": "wikipedia_rest_api"
                        }
        except Exception:
            pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
    }

    last_error = None
    for trust_env in [True, False]:
        try:
            to = httpx.Timeout(8.0, connect=4.0)
            async with httpx.AsyncClient(timeout=to, trust_env=trust_env, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    title = soup.title.get_text(strip=True) if soup.title else url
                    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                        tag.decompose()

                    cleaned_text = re.sub(r"\s+", " ", soup.get_text()).strip()
                    truncated = len(cleaned_text) > 8000
                    content = cleaned_text[:8000] + ("\n... [Content truncated for length]" if truncated else "")

                    return {
                        "url": url,
                        "title": title,
                        "content": content,
                        "character_count": len(cleaned_text),
                        "truncated": truncated
                    }
                else:
                    last_error = f"HTTP {resp.status_code}"
                    break
        except Exception as e:
            err_type = type(e).__name__.lower()
            err_str = str(e) or type(e).__name__
            last_error = f"Connection error: {err_str}"
            low_err = err_str.lower()
            if trust_env and (
                "connecttimeout" in err_type
                or "connecterror" in err_type
                or "proxyerror" in err_type
                or any(k in low_err for k in ("proxy", "socks", "scheme", "unsupportedprotocol", "connect"))
            ):
                continue
            break

    return {
        "error": f"Failed to fetch webpage: {last_error or 'Network timeout'}",
        "url": url,
        "suggestion": "Please try another URL from the web_search results or rely on the search snippets."
    }

def register_utility_tools():
    tool_registry.register(tool_web_search, handle_web_search)
    tool_registry.register(tool_fetch_web_page, handle_fetch_web_page)
    tool_registry.register(tool_datetime, handle_datetime)
    tool_registry.register(tool_calculate, handle_calculate)
    tool_registry.register(tool_search_history, handle_search_history)
    tool_registry.register(tool_get_memory, handle_get_memory)
    tool_registry.register(tool_save_memory, handle_save_memory)

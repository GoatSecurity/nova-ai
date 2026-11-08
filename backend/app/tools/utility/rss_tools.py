import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import httpx
from bs4 import BeautifulSoup

from backend.app.tools.base import BaseTool, ToolParameter
from backend.app.tools.registry import tool_registry
from backend.app.core.logging import logger

CATALOG_PATH = Path(__file__).parent / "rss_catalog.json"
_CATALOG_CACHE: Optional[Dict[str, Any]] = None

# English topic and shorthand alias mapping -> canonical country/category name
CATEGORY_ALIASES: Dict[str, str] = {
    "world": "News",
    "world news": "News",
    "global": "News",
    "global news": "News",
    "international": "News",
    "international news": "News",
    "breaking": "News",
    "breaking news": "News",
    "headlines": "News",
    "top stories": "News",
    "current events": "News",
    "news": "News",
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "america": "United States",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "england": "United Kingdom",
    "ai": "Tech",
    "artificial intelligence": "Tech",
    "machine learning": "Tech",
    "technology": "Tech",
    "tech news": "Tech",
    "dev": "Programming",
    "coding": "Programming",
    "software": "Programming",
    "software engineering": "Programming",
    "web": "Web Development",
    "webdev": "Web Development",
    "frontend": "Web Development",
    "backend": "Web Development",
    "ios": "iOS Development",
    "finance": "Personal finance",
    "money": "Personal finance",
    "economy": "Business & Economy",
    "business": "Business & Economy",
    "markets": "Business & Economy",
    "ui": "UI / UX",
    "ux": "UI / UX",
    "ui/ux": "UI / UX",
    "design": "UI / UX",
    "soccer": "Football",
    "astronomy": "Space",
    "nasa": "Space",
    "cosmos": "Space",
    "cinema": "Movies",
    "film": "Movies",
    "games": "Gaming",
    "videogames": "Gaming",
    "culinary": "Food",
    "recipes": "Food",
    "humor": "Funny",
    "comedy": "Funny",
    "tv": "Television",
    "auto": "Cars",
    "automotive": "Cars",
    "automobile": "Cars",
}

WORLD_SUBFILTER_ALIASES = {"world", "world news", "global", "global news", "international", "international news"}


def load_rss_catalog() -> Dict[str, Any]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        if CATALOG_PATH.exists():
            _CATALOG_CACHE = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        else:
            _CATALOG_CACHE = {"countries": {}, "categories": {}}
    return _CATALOG_CACHE


def _resolve_section(query: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any], List[str]]:
    """
    Resolves a country or category query to (section_type, canonical_name, data_dict, related_matches).
    """
    catalog = load_rss_catalog()
    q_raw = (query or "").strip()
    if not q_raw:
        return None, None, {}, []

    q_lower = q_raw.lower()
    mapped = CATEGORY_ALIASES.get(q_lower) or CATEGORY_ALIASES.get(q_raw)
    search_terms = [mapped.lower(), q_lower] if mapped else [q_lower]

    countries = catalog.get("countries", {})
    categories = catalog.get("categories", {})

    # 1. Exact case-insensitive match
    for term in search_terms:
        for name, data in countries.items():
            if name.lower() == term:
                return "country", name, data, []
        for name, data in categories.items():
            if name.lower() == term:
                return "category", name, data, []

    # 2. Substring / partial match across countries & categories
    matches: List[Tuple[str, str, Dict[str, Any]]] = []
    for name, data in categories.items():
        nl = name.lower()
        if any(t in nl or nl in t for t in search_terms):
            matches.append(("category", name, data))
    for name, data in countries.items():
        nl = name.lower()
        if any(t in nl or nl in t for t in search_terms):
            matches.append(("country", name, data))

    if matches:
        primary_type, primary_name, primary_data = matches[0]
        related = [m[1] for m in matches[1:]]
        return primary_type, primary_name, primary_data, related

    return None, None, {}, []


# --- Tool Definitions ---

tool_list_rss_categories = BaseTool(
    name="list_rss_categories",
    description=(
        "Lists all curated Countries (25) and Topic Categories (34) available in NOVA's built-in RSS directory (~780 feeds). "
        "Use this FIRST to explore the category tree before fetching feed URLs for a specific section."
    ),
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(
            name="filter",
            type="string",
            description="Optional keyword to filter country or category names (e.g. 'Tech', 'Iran', 'Dev')",
            required=False,
        ),
        ToolParameter(
            name="section",
            type="string",
            description="Which branch to list: 'all', 'countries', or 'categories' (default: 'all')",
            required=False,
            default="all",
            enum=["all", "countries", "categories"],
        ),
    ],
)

tool_get_rss_category_feeds = BaseTool(
    name="get_rss_category_feeds",
    description=(
        "Retrieves curated RSS feed titles and URLs for a specific Category or Country from NOVA's RSS tree "
        "(e.g. 'News', 'Tech', 'Programming', 'Iran', 'Science', 'Space', 'Startups', 'United States'). "
        "Note: This lists feed sources only; call fetch_rss_feed next to download actual articles."
    ),
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(
            name="category",
            type="string",
            description="Category or country name (e.g. 'News', 'World News', 'Tech', 'Programming', 'Iran', 'United States')",
        ),
        ToolParameter(
            name="filter",
            type="string",
            description="Optional keyword to filter or prioritize feeds inside the category (e.g. 'world', 'bbc', 'security')",
            required=False,
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of feeds to list from this category (default: 40)",
            required=False,
            default=40,
        ),
    ],
)

tool_fetch_rss_feed = BaseTool(
    name="fetch_rss_feed",
    description=(
        "Fetches and parses live articles/news from a specific RSS/Atom feed URL OR concurrently queries reliable "
        "feeds inside a given RSS category/country. Automatically parses timestamps, sorts freshest items first, "
        "and supports optional keyword filtering across titles and summaries."
    ),
    category="utility",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="Direct RSS or Atom feed URL (obtained from get_rss_category_feeds)",
            required=False,
        ),
        ToolParameter(
            name="category",
            type="string",
            description="Country or category name to read live feeds from (e.g. 'News', 'World News', 'Tech', 'Iran')",
            required=False,
        ),
        ToolParameter(
            name="feed_filter",
            type="string",
            description="Optional filter to select/prioritize specific feeds inside a category (e.g. 'world', 'guardian', 'bbc')",
            required=False,
        ),
        ToolParameter(
            name="query",
            type="string",
            description="Optional keyword filter to match against article titles and descriptions",
            required=False,
        ),
        ToolParameter(
            name="max_items",
            type="integer",
            description="Maximum total articles to return (default: 20, max: 50)",
            required=False,
            default=20,
        ),
        ToolParameter(
            name="max_feeds",
            type="integer",
            description="When querying a category, max number of feeds to fetch concurrently (default: 8, max: 12)",
            required=False,
            default=8,
        ),
    ],
)


# --- Helpers for Fetching & Parsing RSS/Atom ---

def _clean_html_snippet(raw: str, max_len: int = 320) -> str:
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    soup = BeautifulSoup(unescaped, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    if len(text) > max_len:
        return text[:max_len].rstrip() + "..."
    return text


def _strip_xml_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1].lower()
    return tag.lower()


def _parse_feed_xml(xml_text: str, source_name: str, feed_url: str, max_per_feed: int = 10) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not xml_text or not xml_text.strip():
        return items

    # 1. Standard ElementTree parser for clean RSS 2.0 / 1.0 / Atom
    try:
        root = ET.fromstring(xml_text.strip())
        root_name = _strip_xml_ns(root.tag)
        channel_title = source_name

        if root_name == "feed":
            # Atom feed (YouTube, Reddit, GitLab, blogs)
            for child in root:
                cname = _strip_xml_ns(child.tag)
                if cname == "title" and child.text:
                    channel_title = child.text.strip()
                elif cname == "entry":
                    entry = _extract_atom_entry(child, channel_title, feed_url)
                    if entry:
                        items.append(entry)
                        if len(items) >= max_per_feed:
                            break
            if items:
                return items
        else:
            # RSS 2.0 / RDF 1.0
            channel_el = next((c for c in root if _strip_xml_ns(c.tag) == "channel"), None)
            if channel_el is not None:
                title_el = next((c for c in channel_el if _strip_xml_ns(c.tag) == "title"), None)
                if title_el is not None and title_el.text:
                    channel_title = title_el.text.strip()
                rss_items = [c for c in channel_el if _strip_xml_ns(c.tag) == "item"]
            else:
                rss_items = [el for el in root.iter() if _strip_xml_ns(el.tag) == "item"]

            for item_el in rss_items[:max_per_feed]:
                parsed_item = _extract_rss_item(item_el, channel_title, feed_url)
                if parsed_item:
                    items.append(parsed_item)
            if items:
                return items
    except ET.ParseError:
        pass
    except Exception as e:
        logger.debug(f"ElementTree parse fallback for {feed_url}: {e}")

    # 2. Tolerant BeautifulSoup fallback for malformed feeds
    try:
        soup = BeautifulSoup(xml_text, "html.parser")
        raw_items = soup.find_all("item") or soup.find_all("entry")
        for el in raw_items[:max_per_feed]:
            t_tag = el.find("title")
            l_tag = el.find("link")
            link_val = ""
            if l_tag:
                link_val = l_tag.get("href") or l_tag.get_text(strip=True) or ""
            pub_tag = el.find("pubdate") or el.find("published") or el.find("updated") or el.find("dc:date")
            desc_tag = el.find("description") or el.find("summary") or el.find("content")
            title_val = html.unescape(t_tag.get_text(strip=True)) if t_tag else ""
            if title_val or link_val:
                items.append({
                    "source": source_name,
                    "feed_url": feed_url,
                    "title": title_val,
                    "link": link_val.strip(),
                    "published": pub_tag.get_text(strip=True) if pub_tag else "",
                    "summary": _clean_html_snippet(desc_tag.get_text() if desc_tag else ""),
                })
    except Exception as e:
        logger.debug(f"BeautifulSoup RSS fallback failed for {feed_url}: {e}")

    return items


def _extract_rss_item(item_el: ET.Element, source_name: str, feed_url: str) -> Optional[Dict[str, Any]]:
    title = ""
    link = ""
    published = ""
    summary = ""
    for child in item_el:
        tag = _strip_xml_ns(child.tag)
        txt = (child.text or "").strip()
        if tag == "title" and not title:
            title = html.unescape(txt)
        elif tag == "link" and not link:
            link = txt or (child.attrib.get("href") or "").strip()
        elif tag in ("pubdate", "date", "published") and not published:
            published = txt
        elif tag in ("description", "encoded", "summary") and not summary:
            summary = _clean_html_snippet(txt)
    if not (title or link):
        return None
    return {
        "source": source_name,
        "feed_url": feed_url,
        "title": title,
        "link": link,
        "published": published,
        "summary": summary,
    }


def _extract_atom_entry(entry_el: ET.Element, source_name: str, feed_url: str) -> Optional[Dict[str, Any]]:
    title = ""
    link = ""
    published = ""
    summary = ""
    for child in entry_el:
        tag = _strip_xml_ns(child.tag)
        txt = "".join(child.itertext()).strip()
        if tag == "title" and not title:
            title = html.unescape(txt)
        elif tag == "link":
            rel = child.attrib.get("rel", "alternate")
            href = (child.attrib.get("href") or txt or "").strip()
            if href and (not link or rel == "alternate"):
                link = href
        elif tag in ("published", "updated") and not published:
            published = txt
        elif tag in ("summary", "content") and not summary:
            summary = _clean_html_snippet(txt)
    if not (title or link):
        return None
    return {
        "source": source_name,
        "feed_url": feed_url,
        "title": title,
        "link": link,
        "published": published,
        "summary": summary,
    }


def _parse_pubdate_ts(pub_str: str) -> float:
    """Parses RSS RFC-2822 or Atom ISO-8601 date strings to UTC epoch seconds for freshness sorting."""
    if not pub_str:
        return 0.0
    s = pub_str.strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, dt.timestamp())
    except Exception:
        pass
    try:
        iso = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, dt.timestamp())
    except Exception:
        return 0.0


def _select_and_order_feeds(
    feeds: List[Dict[str, Any]],
    feed_filter: str = "",
    strict: bool = False,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Filters or prioritizes feeds matching `feed_filter` inside a category."""
    kw = (feed_filter or "").strip().lower()
    if not kw:
        return feeds, False
    tokens = [t for t in re.split(r"\s+", kw) if t]
    matched: List[Dict[str, Any]] = []
    rest: List[Dict[str, Any]] = []
    for f in feeds:
        hay = f"{f.get('title', '')} {f.get('url', '')} {f.get('domain', '')}".lower()
        if all(t in hay for t in tokens):
            matched.append(f)
        else:
            rest.append(f)
    if strict and matched:
        return matched, True
    if matched:
        return matched + rest, True
    return feeds, False


async def _fetch_single_feed(url: str, source_name: str = "", max_per_feed: int = 12) -> Dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NOVA-RSS-Reader/1.0; +https://github.com/GoatSecurity/nova-ai)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,*;q=0.5",
    }
    last_error = None
    for trust_env in (True, False):
        try:
            to = httpx.Timeout(5.5, connect=3.0)
            async with httpx.AsyncClient(timeout=to, trust_env=trust_env, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    resp.encoding = resp.encoding or "utf-8"
                    items = _parse_feed_xml(resp.text, source_name or url, url, max_per_feed=max_per_feed)
                    return {"url": url, "source": source_name or url, "ok": True, "items": items}
                last_error = f"HTTP {resp.status_code}"
                break
        except Exception as e:
            err_type = type(e).__name__.lower()
            last_error = str(e) or type(e).__name__
            low = last_error.lower()
            is_proxy_or_connect = (
                "connecttimeout" in err_type
                or "connecterror" in err_type
                or "proxyerror" in err_type
                or any(k in low for k in ("proxy", "socks", "scheme", "unsupportedprotocol", "connect"))
            )
            if trust_env and is_proxy_or_connect:
                continue
            break

    return {"url": url, "source": source_name or url, "ok": False, "error": last_error or "Fetch error", "items": []}


# --- Tool Handlers ---

async def handle_list_rss_categories(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    catalog = load_rss_catalog()
    filt = (args.get("filter") or "").strip().lower()
    section = (args.get("section") or "all").lower()

    countries_out = []
    categories_out = []

    if section in ("all", "countries"):
        for name, data in catalog.get("countries", {}).items():
            if not filt or filt in name.lower():
                countries_out.append({
                    "name": name,
                    "display": data.get("display", name),
                    "feed_count": len(data.get("feeds", [])),
                })

    if section in ("all", "categories"):
        for name, data in catalog.get("categories", {}).items():
            if not filt or filt in name.lower():
                categories_out.append({
                    "name": name,
                    "feed_count": len(data.get("feeds", [])),
                })

    return {
        "total_countries": len(countries_out),
        "total_categories": len(categories_out),
        "countries": countries_out,
        "categories": categories_out,
        "next_step": (
            "Call get_rss_category_feeds(category='<name>') to inspect feeds in a branch, "
            "or call fetch_rss_feed(category='<name>') directly to retrieve live articles."
        ),
    }


async def handle_get_rss_category_feeds(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    query = (args.get("category") or "").strip()
    feed_filter = (args.get("filter") or "").strip()
    limit = max(1, min(100, int(args.get("limit") or 40)))
    if not query:
        return {"error": "Please provide a 'category' or country name (call list_rss_categories to see all names)."}

    sec_type, name, data, related = _resolve_section(query)
    if not name:
        catalog = load_rss_catalog()
        return {
            "error": f"No matching country or category found for '{query}'.",
            "available_countries": list(catalog.get("countries", {}).keys()),
            "available_categories": list(catalog.get("categories", {}).keys()),
        }

    # Auto-apply world subfilter if user explicitly queried "world news" etc.
    effective_filter = feed_filter
    if not effective_filter and query.lower() in WORLD_SUBFILTER_ALIASES and name == "News":
        effective_filter = "world"

    all_feeds = data.get("feeds", [])
    selected_feeds, matched_filter = _select_and_order_feeds(all_feeds, effective_filter, strict=True)

    return {
        "section_type": sec_type,
        "category": name,
        "filter_applied": effective_filter if matched_filter else None,
        "related_sections": related,
        "opml_with_category": data.get("opml_with_category", ""),
        "opml_without_category": data.get("opml_without_category", ""),
        "total_feeds": len(all_feeds),
        "matched_feeds": len(selected_feeds),
        "feeds": selected_feeds[:limit],
        "next_step": (
            "DIRECTORY ONLY (articles NOT fetched yet). If the user asked for actual news, headlines, or updates, "
            f"immediately call fetch_rss_feed(category='{name}'"
            + (f", feed_filter='{effective_filter}'" if effective_filter else "")
            + ") or fetch_rss_feed(url='<feed_url>') next before replying."
        ),
    }


def _rank_and_diversify_items(
    all_items: List[Dict[str, Any]],
    query: str,
    max_items: int,
) -> Tuple[List[Dict[str, Any]], int]:
    """Ranks items by query match + freshness, drops stale dead-feed outliers, and diversifies sources."""
    enriched: List[Tuple[float, Dict[str, Any]]] = []
    seen_titles = set()
    for it in all_items:
        norm_title = re.sub(r"\W+", "", (it.get("title") or "").lower())[:64]
        if norm_title and norm_title in seen_titles:
            continue
        if norm_title:
            seen_titles.add(norm_title)
        ts = _parse_pubdate_ts(it.get("published", ""))
        enriched.append((ts, it))

    # Drop ancient stale feeds (e.g. frozen 2023 feeds) when recent items (< 90 days) exist
    max_ts = max((ts for ts, _ in enriched), default=0.0)
    if max_ts > 0:
        fresh_cutoff = max_ts - (90 * 86400)
        fresh_only = [(ts, it) for ts, it in enriched if ts == 0.0 or ts >= fresh_cutoff]
        if len(fresh_only) >= min(4, len(enriched)):
            enriched = fresh_only

    if query:
        q_lower = query.lower().strip()
        q_terms = [t for t in re.split(r"[\s,]+", q_lower) if len(t) >= 2]
        scored: List[Tuple[int, int, float, Dict[str, Any]]] = []
        for ts, it in enriched:
            title_l = (it.get("title") or "").lower()
            summ_l = (it.get("summary") or "").lower()
            src_l = (it.get("source") or "").lower()
            blob = f"{title_l} {summ_l} {src_l}"
            matched_terms = sum(1 for t in q_terms if t in blob)
            if matched_terms > 0:
                phrase_bonus = 5 if q_lower in blob else 0
                title_hits = sum(2 for t in q_terms if t in title_l)
                scored.append((matched_terms, phrase_bonus + title_hits, ts, it))
        scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        matched_items = [x[3] for x in scored]
        return matched_items[:max_items], len(matched_items)

    # No keyword query: group by source, sort newest-first inside each source, then round-robin interleave
    by_source: Dict[str, List[Tuple[float, Dict[str, Any]]]] = {}
    for ts, it in enriched:
        src = it.get("source") or it.get("feed_url") or "RSS"
        by_source.setdefault(src, []).append((ts, it))
    for lst in by_source.values():
        lst.sort(key=lambda x: x[0], reverse=True)

    ordered_sources = sorted(
        by_source.keys(),
        key=lambda s: by_source[s][0][0] if by_source[s] else 0.0,
        reverse=True,
    )

    interleaved: List[Dict[str, Any]] = []
    idx = 0
    while len(interleaved) < max_items:
        added_this_round = False
        for src in ordered_sources:
            lst = by_source[src]
            if idx < len(lst):
                interleaved.append(lst[idx][1])
                added_this_round = True
                if len(interleaved) >= max_items:
                    break
        if not added_this_round:
            break
        idx += 1

    return interleaved, len(interleaved)


async def handle_fetch_rss_feed(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    url = (args.get("url") or "").strip()
    category = (args.get("category") or "").strip()
    feed_filter = (args.get("feed_filter") or "").strip()
    query = (args.get("query") or "").strip()
    max_items = max(1, min(50, int(args.get("max_items") or 20)))
    max_feeds = max(1, min(12, int(args.get("max_feeds") or 8)))

    if not url and not category:
        return {"error": "Provide either a direct RSS feed 'url' or a 'category' name (e.g. 'News', 'World News', 'Tech', 'Iran')."}

    targets: List[Tuple[str, str]] = []
    resolved_cat_name = None

    if url:
        targets.append((url, url))
    elif category:
        _, resolved_cat_name, data, _ = _resolve_section(category)
        if not resolved_cat_name:
            return {"error": f"Category or country '{category}' not found in RSS directory. Call list_rss_categories first."}
        effective_filter = feed_filter
        if not effective_filter and category.lower() in WORLD_SUBFILTER_ALIASES and resolved_cat_name == "News":
            effective_filter = "world"
        ordered_feeds, _ = _select_and_order_feeds(data.get("feeds", []), effective_filter, strict=False)
        for f in ordered_feeds[:max_feeds]:
            if f.get("url"):
                targets.append((f["url"], f.get("title") or f["url"]))

    # Always parse enough items per feed BEFORE applying query filtering (prevents missing deep headlines)
    per_feed_limit = max(25, max_items) if query else (max_items if len(targets) == 1 else max(8, (max_items // max(1, len(targets))) + 5))
    results = await asyncio.gather(
        *[_fetch_single_feed(u, title, max_per_feed=per_feed_limit) for u, title in targets],
        return_exceptions=True,
    )

    all_items: List[Dict[str, Any]] = []
    feed_statuses: List[Dict[str, Any]] = []
    for res in results:
        if isinstance(res, Exception):
            feed_statuses.append({"ok": False, "error": str(res)})
            continue
        feed_statuses.append({
            "source": res.get("source"),
            "url": res.get("url"),
            "ok": res.get("ok"),
            "item_count": len(res.get("items", [])),
            **({"error": res["error"]} if res.get("error") else {}),
        })
        all_items.extend(res.get("items", []))

    final_items, matched_total = _rank_and_diversify_items(all_items, query=query, max_items=max_items)

    resp: Dict[str, Any] = {
        "category": resolved_cat_name,
        "feeds_checked": len(targets),
        "feeds_succeeded": sum(1 for s in feed_statuses if s.get("ok") and s.get("item_count", 0) > 0),
        "feed_statuses": feed_statuses,
        "total_fetched": len(all_items),
        "items": final_items,
    }
    if query:
        resp["query"] = query
        resp["matched_count"] = matched_total
        if matched_total == 0 and all_items:
            fallback_items, _ = _rank_and_diversify_items(all_items, query="", max_items=min(10, max_items))
            resp["note"] = "No exact keyword match in fetched headlines; returning freshest headlines across live feeds below."
            resp["latest_sample"] = fallback_items
    return resp


def register_rss_tools():
    tool_registry.register(tool_list_rss_categories, handle_list_rss_categories)
    tool_registry.register(tool_get_rss_category_feeds, handle_get_rss_category_feeds)
    tool_registry.register(tool_fetch_rss_feed, handle_fetch_rss_feed)

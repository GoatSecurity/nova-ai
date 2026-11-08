---
name: RSS Feeds Explorer
command: /rss
description: Browse curated country & topic RSS feed trees and fetch live news/articles
icon: rss
color: orange
is_builtin: true
---

Activate RSS Feeds Explorer mode: Follow NOVA's hierarchical RSS Tree workflow end-to-end to deliver verified live news and articles:
1. Inspect the relevant branch using `get_rss_category_feeds(category="<Country or Topic>", filter="<optional subtopic>")` (e.g. `category="News", filter="world"` for World News, or `list_rss_categories` if browsing all branches).
2. Unless the user ONLY asked for raw feed URLs, NEVER stop after listing directory links: immediately call `fetch_rss_feed(category="<category>", feed_filter="<subtopic>", query="<optional keywords>", max_items=20)` or `fetch_rss_feed(url="<feed_url>")` to download live articles.
3. Read the parsed headlines, dates, summaries, and links returned by `fetch_rss_feed` and present a thorough, organized synthesis in the user's exact language with source names and direct links.
4. Combine with `web_search` when additional background is needed, and NEVER invoke shell/PowerShell/Python commands to scrape publisher websites.

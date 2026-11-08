import pytest
from backend.app.tools.registry import tool_registry
from backend.app.tools.utility.rss_tools import (
    _parse_feed_xml,
    _resolve_section,
    _rank_and_diversify_items,
)
from backend.app.agent.prompt_engine import PromptEngine
from backend.app.agent.orchestrator import _format_tool_feedback, _scrub_internal_markers
from backend.app.agent.context_manager import ContextManager


@pytest.mark.asyncio
async def test_rss_directory_tree_tools():
    # 1. List root categories & countries
    tree = await tool_registry.execute_tool("list_rss_categories", {}, {})
    assert tree["total_countries"] == 25
    assert tree["total_categories"] == 34

    country_names = [c["name"] for c in tree["countries"]]
    category_names = [c["name"] for c in tree["categories"]]
    assert "Iran" in country_names
    assert "Tech" in category_names
    assert "Programming" in category_names

    # 2. Filtered root listing
    filtered = await tool_registry.execute_tool("list_rss_categories", {"filter": "android"}, {})
    assert any(c["name"] == "Android" for c in filtered["categories"])
    assert any(c["name"] == "Android Development" for c in filtered["categories"])

    # 3. Drill down into branch using canonical names and English aliases
    iran_feeds = await tool_registry.execute_tool("get_rss_category_feeds", {"category": "Iran"}, {})
    assert iran_feeds["category"] == "Iran"
    assert iran_feeds["total_feeds"] == 7
    assert any("yjc.ir" in f["url"] for f in iran_feeds["feeds"])

    world_feeds = await tool_registry.execute_tool("get_rss_category_feeds", {"category": "world news", "filter": "world"}, {})
    assert world_feeds["category"] == "News"
    assert len(world_feeds["feeds"]) >= 4
    assert any("bbc" in f["url"].lower() for f in world_feeds["feeds"])

    tech_feeds = await tool_registry.execute_tool("get_rss_category_feeds", {"category": "Tech"}, {})
    assert tech_feeds["category"] == "Tech"
    assert tech_feeds["total_feeds"] >= 20


def test_rss_and_atom_xml_parsing():
    rss_xml = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Test Tech News</title>
        <item>
          <title>Local AI Agents Reach Milestone</title>
          <link>https://example.com/article-1</link>
          <pubDate>Tue, 10 Nov 2026 10:00:00 GMT</pubDate>
          <description>&lt;p&gt;Full summary of &lt;b&gt;local AI&lt;/b&gt; capabilities.&lt;/p&gt;</description>
        </item>
      </channel>
    </rss>"""
    parsed_rss = _parse_feed_xml(rss_xml, "TestFeed", "https://example.com/rss")
    assert len(parsed_rss) == 1
    assert parsed_rss[0]["title"] == "Local AI Agents Reach Milestone"
    assert parsed_rss[0]["link"] == "https://example.com/article-1"
    assert "Full summary of local AI capabilities." in parsed_rss[0]["summary"]

    atom_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Atom Feed</title>
      <entry>
        <title>Python 3.14 Features</title>
        <link rel="alternate" href="https://example.com/py314"/>
        <updated>2026-11-10T12:00:00Z</updated>
        <summary>Release notes overview.</summary>
      </entry>
    </feed>"""
    parsed_atom = _parse_feed_xml(atom_xml, "AtomSrc", "https://example.com/atom")
    assert len(parsed_atom) == 1
    assert parsed_atom[0]["title"] == "Python 3.14 Features"
    assert parsed_atom[0]["link"] == "https://example.com/py314"


@pytest.mark.asyncio
async def test_prompt_engine_includes_rss_categories_and_skill():
    sec_type, cname, _, _ = _resolve_section("coding")
    assert sec_type == "category"
    assert cname == "Programming"

    sec_world, cname_world, _, _ = _resolve_section("world news")
    assert sec_world == "category"
    assert cname_world == "News"

    sp = await PromptEngine.build_system_prompt(skill_command="/rss")
    assert "CURATED RSS FEEDS DIRECTORY" in sp
    assert "Iran" in sp
    assert "Programming" in sp
    assert "RSS FEEDS EXPLORER (/rss)" in sp


def test_rss_ranking_freshness_and_formatting():
    sample_items = [
        {"source": "BBC News", "title": f"BBC Story {i}", "published": f"Tue, 10 Nov 2026 10:0{i}:00 GMT", "summary": "World summit news" if i == 9 else "General news", "link": f"https://bbc.co.uk/{i}"}
        for i in range(10)
    ] + [
        {"source": "Guardian", "title": "Guardian Breaking", "published": "Tue, 10 Nov 2026 11:00:00 GMT", "summary": "Latest Europe update", "link": "https://theguardian.com/1"},
        {"source": "Legacy Feed", "title": "Stale 2023 Story", "published": "Fri, 14 Apr 2023 20:00:28 GMT", "summary": "Old news", "link": "https://cnn.com/old"},
    ]

    # Freshness + source interleaving drops stale 2023 feed and interleaves sources
    ranked, total = _rank_and_diversify_items(sample_items, query="", max_items=5)
    assert total == 5
    assert all("2023 Story" not in it["title"] for it in ranked)
    sources = {it["source"] for it in ranked}
    assert "Guardian" in sources and "BBC News" in sources

    # Keyword query finds item #9 accurately and orchestrator feedback renders Markdown
    q_ranked, q_total = _rank_and_diversify_items(sample_items, query="summit", max_items=5)
    assert q_total == 1
    assert q_ranked[0]["title"] == "BBC Story 9"

    fb = _format_tool_feedback("fetch_rss_feed", {
        "category": "News",
        "feeds_checked": 2,
        "total_fetched": 2,
        "feed_statuses": [{"source": "BBC News", "ok": True, "item_count": 1}],
        "items": q_ranked,
    })
    assert "RSS Live Articles Digest" in fb
    assert "BBC Story 9" in fb
    assert "Synthesize a clear, comprehensive response" in fb


def test_context_manager_preserves_system_prompt_and_scrubs_markers():
    assert _scrub_internal_markers("Executing system tool operation...\nHello world") == "Hello world"
    assert _scrub_internal_markers("[Called tools: fetch_rss_feed]\nDone.") == "Done."

    sys_msg = {"role": "system", "content": "CRITICAL SYSTEM PROMPT"}
    msgs = [sys_msg] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": "X" * 3000}
        for i in range(10)
    ]
    pruned, _ = ContextManager.prune_context(sys_msg["content"], msgs, max_context_tokens=2000, reserve_response_tokens=500)
    assert pruned[0]["role"] == "system"
    assert pruned[0]["content"] == "CRITICAL SYSTEM PROMPT"

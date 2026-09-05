"""Analytics must count people, not crawlers — and the prerendered copy must not flash.

The owner compared the admin numbers with Shopify: 2789 tracked page views contained 1769 bot hits
(63%), and `sessionStorage` made every new browser tab a new session.
"""
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import analytics_bots                    # noqa: E402
import prerender                         # noqa: E402
import server                            # noqa: E402

HUMANS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36",
]
BOTS = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
    "Mozilla/5.0 (compatible; SemrushBot/7~bl)",
    "GPTBot/1.0 (+https://openai.com/gptbot)",
    "ClaudeBot/1.0",
    "PerplexityBot/1.0",
    "Bytespider",
    "facebookexternalhit/1.1",
    "TelegramBot (like TwitterBot)",
    "python-requests/2.33.1",
    "curl/8.5.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/126.0 Safari/537.36",
    "Better Uptime Bot",
    "Pingdom.com_bot_version_1.4",
    "",
]


def test_every_known_crawler_is_detected():
    for ua in BOTS:
        assert analytics_bots.is_bot(ua), ua


def test_real_browsers_are_not_flagged():
    for ua in HUMANS:
        assert not analytics_bots.is_bot(ua), ua


def test_the_mongo_filter_excludes_bots_and_empty_agents():
    f = analytics_bots.NOT_BOT
    assert f["bot"] == {"$ne": True}
    assert f["ua"]["$not"]["$regex"] == analytics_bots.BOT_PATTERN
    assert "" in f["ua"]["$nin"]


def test_three_visitor_cookies_with_24h_7d_and_30d():
    windows = dict(server.VISITOR_COOKIES)
    assert windows == {"pp_v24": 86400, "pp_v7": 604800, "pp_v30": 2592000}


def test_the_prerendered_copy_is_hidden_from_a_human_but_visible_without_javascript():
    out = prerender._inject('<html><head></head><body><div id="root"></div></body></html>',
                            "<title>x</title>", "<h1>Продукт</h1>")
    assert '<div id="pp-prerender"><h1>Продукт</h1></div>' in out
    assert "clip:rect(0 0 0 0)" in out and "<noscript>" in out
    # the noscript rule must undo the hiding, otherwise a JS-less visitor gets a blank page
    noscript = out.split("<noscript>")[1].split("</noscript>")[0]
    assert "position:static" in noscript


def test_conversion_ignores_the_imported_shopify_history():
    src = open(os.path.join(os.path.dirname(__file__), "..", "server.py"), encoding="utf-8").read()
    assert 'own_orders = sum(1 for o in orders if (o.get("source") or "storefront") != "shopify_import")' in src
    assert '"conversion": (min(round(own_orders / len(sessions) * 100, 2), 100.0)' in src

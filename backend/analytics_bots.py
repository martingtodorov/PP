"""Bot detection for the shop analytics.

Shopify never counts crawlers; we did, which is why the session numbers were several times higher.
Every visit is still stored, but a bot hit is flagged and excluded from every analytics figure.
"""
import re

# search engines, SEO tools, AI crawlers, social unfurlers, uptime monitors, HTTP libraries,
# headless browsers and security scanners — the whole list is deliberately aggressive
BOT_PATTERN = (
    r"bot\b|bots?[/ ]|crawl|spider|scrap|slurp|archiver|fetcher|preview|"
    r"google(?!chrome)|bingpreview|adsbot|mediapartners|apis-google|feedfetcher|duckduck|"
    r"yandex|baidu|sogou|exabot|seznam|qwant|petal|coccoc|naver|"
    r"ahrefs|semrush|majestic|mj12|dotbot|blexbot|dataforseo|serpstat|sistrix|screaming ?frog|"
    r"moz\.com|rogerbot|linkdex|spyfu|barkrowler|neevabot|zoominfo|"
    r"gptbot|oai-searchbot|chatgpt|claude|anthropic|perplexity|ccbot|"
    r"bytespider|amazonbot|applebot|youbot|diffbot|meta-external|"
    r"facebookexternalhit|facebot|whatsapp|telegram|twitterbot|linkedinbot|slackbot|discord|"
    r"pinterest|redditbot|tumblr|vkshare|skypeuripreview|embedly|quora|"
    r"lighthouse|pagespeed|gtmetrix|pingdom|uptime|monitor|statuscake|newrelic|site24x7|"
    r"zabbix|nagios|datadog|checkly|betteruptime|"
    r"headless|phantomjs|puppeteer|playwright|selenium|electron/|"
    r"python|curl/|wget|libwww|java/|okhttp|go-http|axios|node-fetch|got \(|guzzle|"
    r"httpclient|httpx|requests|restsharp|postman|insomnia|apache-httpclient|"
    r"censys|shodan|zgrab|masscan|nmap|nuclei|expanse|paloalto|internet-?measurement"
)
BOT_RE = re.compile(BOT_PATTERN, re.I)

# a visit without a user agent is never a real browser
NOT_BOT = {"bot": {"$ne": True},
           "ua": {"$not": {"$regex": BOT_PATTERN, "$options": "i"}, "$nin": ["", None]}}


def is_bot(ua: str) -> bool:
    ua = (ua or "").strip()
    return not ua or bool(BOT_RE.search(ua))

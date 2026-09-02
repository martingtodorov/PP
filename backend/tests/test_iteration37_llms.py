"""Iteration 37: llms.txt + CLS-related SEO endpoints (robots, sitemap_agentic, agents.md)"""
import os
import re
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")


def test_api_llms_txt():
    r = requests.get(f"{BASE_URL}/api/llms.txt", timeout=30)
    assert r.status_code == 200, r.text[:200]
    ctype = r.headers.get("content-type", "")
    assert "text/markdown" in ctype, f"content-type={ctype}"
    body = r.text
    # H1
    lines = [l for l in body.splitlines() if l.strip()]
    assert lines[0].startswith("# PurePeptide"), f"first non-empty line: {lines[0]!r}"
    # only one H1
    h1_count = sum(1 for l in body.splitlines() if re.match(r"^# [^#]", l))
    assert h1_count == 1, f"expected exactly one H1, got {h1_count}"
    # blockquote summary
    assert re.search(r"(?m)^>\s+\S", body), "no blockquote summary found"
    # Store / Collections / Products sections (H2)
    assert re.search(r"(?mi)^##\s+Store", body), "missing Store section"
    assert re.search(r"(?mi)^##\s+Collections", body), "missing Collections section"
    assert re.search(r"(?mi)^##\s+Products", body), "missing Products section"
    # Contains markdown link list entries
    assert re.search(r"- \[.+\]\(https?://[^\)]+/products/[^\)]+\)", body), "no product markdown link with handle"
    # EUR prices somewhere in product list
    assert re.search(r"€\s?\d", body) or re.search(r"\bEUR\b", body), "no EUR price shown"


def test_static_root_llms_txt():
    r = requests.get(f"{BASE_URL}/llms.txt", timeout=30)
    assert r.status_code == 200, r.status_code
    body = r.text.lstrip()
    assert body.startswith("# PurePeptide"), f"body starts with: {body[:80]!r}"


def test_robots_mentions_llms():
    r = requests.get(f"{BASE_URL}/api/robots.txt", timeout=30)
    assert r.status_code == 200
    assert "llms.txt" in r.text, "robots.txt does not mention llms.txt"


def test_agentic_sitemap_has_llms():
    r = requests.get(f"{BASE_URL}/api/sitemap_agentic_discovery.xml", timeout=30)
    assert r.status_code == 200
    assert "/llms.txt" in r.text, "agentic sitemap missing /llms.txt"


def test_agents_md_still_ok():
    r = requests.get(f"{BASE_URL}/api/agents.md", timeout=30)
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    assert "text/markdown" in ctype or "text/plain" in ctype, ctype
    assert len(r.text) > 50

"""No third-party trackers in the shell, and the hero is preloaded only where it is used."""
import pathlib

import requests

API = "http://localhost:8001/api"
INDEX = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public" / "index.html"


def test_the_shell_loads_no_posthog():
    """PostHog fired a cross-origin /flags call that the browser blocked, and recorded sessions
    of real customers from a key that is not ours."""
    html = INDEX.read_text()
    assert "posthog" not in html.lower()
    assert "i.posthog.com" not in html


def test_the_hero_is_not_preloaded_site_wide():
    assert "hero-home.webp" not in INDEX.read_text()


def test_the_hero_is_preloaded_on_the_home_page_only():
    def page(path):
        return requests.get(f"{API}/seo/prerender", params={"path": path},
                            headers={"Host": "purepeptide.bg"}, timeout=30).text

    assert 'href="/hero-home.webp"' in page("/")
    for path in ("/pages/faq", "/collections", "/pages/html-sitemap"):
        assert "hero-home.webp" not in page(path), path

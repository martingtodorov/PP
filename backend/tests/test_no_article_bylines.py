"""The owner's rule: no author names anywhere on the site — not in the list, not in the JSON-LD."""
import requests

API = "http://localhost:8001/api"
NAMES = ("Georgi Mladenov", "Martin Todorov")


def test_the_article_list_carries_no_byline():
    arts = requests.get(f"{API}/articles", timeout=20).json()["articles"]
    assert arts
    assert all("author" not in a for a in arts)


def test_a_single_article_carries_no_byline():
    handle = requests.get(f"{API}/articles", timeout=20).json()["articles"][0]["handle"]
    art = requests.get(f"{API}/articles/{handle}", timeout=20).json()["article"]
    assert "author" not in art
    assert not any(n in str(art) for n in NAMES)


def test_the_rendered_article_credits_the_brand_only():
    handle = requests.get(f"{API}/articles", timeout=20).json()["articles"][0]["handle"]
    r = requests.get(f"{API}/seo/prerender", params={"path": f"/articles/{handle}"},
                     headers={"Host": "purepeptide.bg"}, timeout=20)
    assert r.status_code == 200
    assert '"author": {"@type": "Organization", "name": "PurePeptide"}' in r.text
    assert not any(n in r.text for n in NAMES)

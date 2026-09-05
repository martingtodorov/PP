"""Two deploy-time guarantees: no dead URL in a sitemap, no shrunken rotation.

The owner: "нищо не проверява, че URL-ите в sitemap-а са живи … самият факт, че мъртъв URL може да
стигне до публикуван sitemap, е дефект" and "when rotating product descriptions I want you to keep
the same general description length and heading names. Youve cut them down too much".
"""
import os
import pathlib
import subprocess
import sys

import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import i18n                               # noqa: E402

BACKEND = pathlib.Path(__file__).resolve().parent.parent
PLAYBOOK = (BACKEND.parent / "deploy/hetzner/ansible/playbooks/deploy_backend.yml").read_text("utf-8")

ORIGINAL = """<h1 class="p1">Какво е Sermorelin?</h1>
<p>Sermorelin е синтетичен аналог на GHRH с 29 аминокиселини. Той стимулира хипофизата да
отделя собствен растежен хормон. Изследванията го използват при модели на застаряване.</p>
<h2>Механизъм на действие</h2>
<p>Свързва се с GHRH рецептора. Ефектът е пулсативен и запазва физиологичния ритъм.</p>
<ul><li>Доза в изследвания: 100-300 mcg</li><li>Чистота >99%</li></ul>"""


def test_every_sitemap_url_is_alive():
    """The same check the deploy runs — a red build here means a dead URL would go public."""
    res = subprocess.run([sys.executable, "scripts/check_sitemap.py",
                          "--base", "http://127.0.0.1:8001"],
                         cwd=BACKEND, capture_output=True, text=True, timeout=600)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "0 broken" in res.stdout and "every sitemap URL answers 200" in res.stdout


def test_the_deploy_fails_when_a_sitemap_url_is_dead():
    assert "scripts/check_sitemap.py" in PLAYBOOK
    assert "failed_when: sitemap_check.rc != 0" in PLAYBOOK


def test_the_router_pages_answer_too():
    """/pages/articles and the HTML sitemaps live in the router, so they were soft 404s."""
    import requests

    for path in ("/pages/articles", "/pages/html-sitemap", "/pages/html-sitemap-blogs"):
        r = requests.get("http://127.0.0.1:8001/api/seo/prerender", params={"path": path},
                         headers={"Host": "purepeptide.bg"}, timeout=30)
        assert r.status_code == 200, (path, r.status_code)
        assert "<li><a" in r.text, path


def test_a_shortened_rewrite_is_rejected():
    short = """<h1 class="p1">Какво е Sermorelin?</h1><p>Sermorelin е аналог на GHRH.</p>
<h2>Механизъм на действие</h2><p>Свързва се с рецептора.</p>
<ul><li>100-300 mcg</li><li>Чистота >99%</li></ul>"""
    with pytest.raises(RuntimeError, match="скъсен"):
        i18n.check_rewrite(ORIGINAL, short)


def test_a_renamed_heading_is_rejected():
    renamed = ORIGINAL.replace("Механизъм на действие", "Как работи")
    with pytest.raises(RuntimeError, match="заглавията"):
        i18n.check_rewrite(ORIGINAL, renamed)


def test_a_faithful_rewrite_passes():
    ok = ORIGINAL.replace(
        "Sermorelin е синтетичен аналог на GHRH с 29 аминокиселини.",
        "Sermorelin представлява синтетичен GHRH аналог, изграден от 29 аминокиселини.")
    i18n.check_rewrite(ORIGINAL, ok)          # must not raise
    assert i18n.headings_of(ORIGINAL) == ["Какво е Sermorelin?", "Механизъм на действие"]


def test_the_prompt_states_both_rules():
    src = (BACKEND / "i18n.py").read_text("utf-8")
    assert "Reproduce every heading VERBATIM" in src
    assert "Keep the LENGTH." in src and "Never summarise" in src

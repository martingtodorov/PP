"""A link rotation may change the URL and the copy — never the SEO title and description.

The meta tags fall back to the title / the description when the SEO fields are empty, so the
rotation pins the current wording into the fields before the AI rewrite (owner's decision 12.06.2026).
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")

from conftest import LOOP  # noqa: E402  (one shared loop, see tests/conftest.py)

import server  # noqa: E402
from prerender import _text  # noqa: E402

DESC = ("<h1>Какво е тестовият пептид?</h1>\n<p>Тестовият пептид е изследван за ефекти върху "
        "възстановяването и метаболизма. Проучванията са само за лабораторна употреба.</p>")
REWRITTEN = ("<h1>Какво е тестовият пептид?</h1>\n<p>За тестовия пептид има проведени изследвания "
             "върху ефектите му върху метаболизма и възстановяването. Проучванията се провеждат "
             "единствено за лабораторна употреба.</p>")
run = LOOP.run_until_complete


def _make(seo_title="", seo_description="", handle="zz-seo-rotation"):
    run(server.db.products.delete_many({"handle": {"$regex": f"^{handle}"}}))
    run(server.db.products.insert_one({
        "id": "zz-seo-rotation-1", "handle": handle, "title": "Тестов пептид 5mg",
        "description": DESC, "seo_title": seo_title, "seo_description": seo_description,
        "variants": [{"name": "5mg", "price_eur": 10.0, "stock": 1, "sku": "ZZ-SEO"}], "active": True}))


def _cleanup(handle="zz-seo-rotation"):
    run(server.db.products.delete_many({"id": "zz-seo-rotation-1"}))
    run(server.db.delisted_links.delete_many({"url": {"$regex": handle}}))
    run(server.db.rotation_log.delete_many({"handle": {"$regex": f"^{handle}"}}))


def _rotate(monkeypatch, handle="zz-seo-rotation"):
    async def fake_rewrite(html, locale, context=""):
        return REWRITTEN

    monkeypatch.setattr(server, "ai_rewrite_html", fake_rewrite)
    res = run(server.rotate_content("products", handle, "bg", "test@purepeptide.bg"))
    doc = run(server.db.products.find_one({"id": "zz-seo-rotation-1"}, {"_id": 0}))
    return res, doc


def test_empty_seo_fields_are_pinned_so_the_meta_tags_do_not_move(monkeypatch):
    try:
        _make()
        res, doc = _rotate(monkeypatch)
        assert res["rewritten"] is True
        assert doc["seo_title"] == "Тестов пептид 5mg"
        assert doc["seo_description"] == _text(DESC)
        loc = server.localize_doc(doc, "bg")
        assert loc["description"] == REWRITTEN          # the copy did change
        assert loc["seo_title"] == "Тестов пептид 5mg"  # the meta did not
        assert loc["seo_description"] == _text(DESC)
    finally:
        _cleanup()


def test_the_owners_own_seo_text_is_never_overwritten(monkeypatch):
    try:
        _make(seo_title="IGF-LR3 – пептид с анаболен ефект | цена",
              seo_description="IGF-LR3, изследван за ефекти върху растежния хормон.")
        res, doc = _rotate(monkeypatch)
        assert res["rewritten"] is True
        assert doc["seo_title"] == "IGF-LR3 – пептид с анаболен ефект | цена"
        assert doc["seo_description"] == "IGF-LR3, изследван за ефекти върху растежния хормон."
    finally:
        _cleanup()


def test_restoring_an_old_handle_touches_neither_copy_nor_meta(monkeypatch):
    """`to=` republishes an exact handle — no rewrite, so there is nothing to pin."""
    try:
        _make()

        async def boom(*a, **kw):
            raise AssertionError("the rewrite must not run when a handle is restored")

        monkeypatch.setattr(server, "ai_rewrite_html", boom)
        res = run(server.rotate_content("products", "zz-seo-rotation", "bg", "t@t.bg",
                                        to="zz-seo-rotation-old"))
        doc = run(server.db.products.find_one({"id": "zz-seo-rotation-1"}, {"_id": 0}))
        assert res["rewritten"] is False
        assert doc["description"] == DESC
        assert doc["seo_title"] == "" and doc["seo_description"] == ""
    finally:
        _cleanup()


def test_the_ai_may_not_rename_a_heading():
    from i18n import check_rewrite

    check_rewrite(DESC, REWRITTEN)              # same headings, same length — accepted
    renamed = REWRITTEN.replace("Какво е тестовият пептид?", "Какво представлява тестовият пептид?")
    try:
        check_rewrite(DESC, renamed)
        raise AssertionError("a renamed heading must be rejected")
    except RuntimeError as exc:
        assert "заглавията" in str(exc)

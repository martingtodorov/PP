"""The prerendered HTML and the API must agree on what is live.

A draft article / de-activated product used to be served to Googlebot as 200 + index, follow with
the full copy and Article schema, while the API answered 404 and the React page then set
„noindex" — a soft 404 that GSC reports as „Excluded by 'noindex' tag" on a URL the server presents
as alive (owner's report, 24.06.2026).
"""
import uuid

import prerender
import server
from conftest import run

LOC = "bg"


def _run_prerender(path):
    return run(prerender.render(path, "purepeptide.bg"))


def test_a_draft_article_is_a_404_for_the_crawler_too():
    handle = f"pytest-draft-{uuid.uuid4().hex[:6]}"
    run(server.db.articles.insert_one({
        "id": str(uuid.uuid4()), "handle": handle, "title": "Чернова", "body": "<p>текст</p>",
        "locale": LOC, "published": False, "published_at": "2026-06-01T00:00:00+00:00"}))
    try:
        assert run(prerender._article(LOC, handle)) is None
        assert run(server.db.articles.find_one({"handle": handle}))          # it is still there
    finally:
        run(server.db.articles.delete_one({"handle": handle}))


def test_a_published_article_is_still_rendered():
    handle = f"pytest-live-{uuid.uuid4().hex[:6]}"
    run(server.db.articles.insert_one({
        "id": str(uuid.uuid4()), "handle": handle, "title": "Жива статия", "body": "<p>текст</p>",
        "locale": LOC, "published": True, "published_at": "2026-06-01T00:00:00+00:00"}))
    try:
        out = run(prerender._article(LOC, handle))
        assert out and "Жива статия" in out["body"]
    finally:
        run(server.db.articles.delete_one({"handle": handle}))


def test_a_deactivated_product_is_a_404_for_the_crawler_and_the_api():
    handle = f"pytest-off-{uuid.uuid4().hex[:6]}"
    run(server.db.products.insert_one({
        "id": str(uuid.uuid4()), "handle": handle, "title": "Спрян продукт", "price_eur": 10.0,
        "active": False, "variants": [{"title": "5mg", "price_eur": 10.0, "sku": "OFF-5"}]}))
    try:
        assert run(prerender._product(LOC, handle)) is None
        try:
            run(server.get_product(handle, LOC))
            raise AssertionError("the API served a de-activated product")
        except server.HTTPException as exc:
            assert exc.status_code == 404
    finally:
        run(server.db.products.delete_one({"handle": handle}))


def test_a_product_without_the_active_flag_is_treated_as_live():
    """Imported products may not carry `active` at all — `active: True` used to 404 them."""
    handle = f"pytest-imported-{uuid.uuid4().hex[:6]}"
    run(server.db.products.insert_one({
        "id": str(uuid.uuid4()), "handle": handle, "title": "Внесен продукт", "price_eur": 10.0,
        "variants": [{"title": "5mg", "price_eur": 10.0, "sku": "IMP-5"}]}))
    try:
        assert run(prerender._product(LOC, handle)) is not None
    finally:
        run(server.db.products.delete_one({"handle": handle}))


def test_a_delisted_collection_is_a_404_for_the_crawler():
    handle = f"pytest-col-{uuid.uuid4().hex[:6]}"
    run(server.db.collections_cat.insert_one({
        "id": str(uuid.uuid4()), "handle": handle, "title": "Скрита колекция", "delisted": True}))
    try:
        assert run(prerender._collection(LOC, handle)) is None
    finally:
        run(server.db.collections_cat.delete_one({"handle": handle}))

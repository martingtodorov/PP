"""Renaming a live URL from the admin: it must succeed, retire the old URL and keep the order.

Three bugs the owner hit on 21.06.2026:
  * the rename wrote the new handle FIRST, so the rotation looked the product up by a handle that
    no longer existed and answered 404 „Няма съдържание с handle“ — the URL changed anyway, with no
    rotation recorded, and the product was unreachable under the URL he had just typed;
  * the manual product order is a list of handles, so the renamed product dropped to the end;
  * the catch-all collection printed „Всички пептиди“ twice (our H1 + the heading of the copy).
"""
import uuid

import server
from conftest import run
from prerender import drop_leading_heading


def _product(handle):
    return {"id": str(uuid.uuid4()), "handle": handle, "title": "Retatrutide 5mg",
            "price_eur": 99.0, "collections": ["secretagogues"], "active": True,
            "description": "<p>Retatrutide за научни изследвания.</p>"}


def _rename(doc, new_handle):
    run(server._republish_handle("products", doc, new_handle, "pytest@purepeptide.bg"))
    return run(server.db.products.find_one({"id": doc["id"]}, {"_id": 0}))


def test_a_rename_publishes_the_typed_url_and_retires_the_old_one():
    doc = _product(f"21-retatrutide-5-{uuid.uuid4().hex[:3]}")
    run(server.db.products.insert_one(doc.copy()))
    try:
        after = _rename(doc, "retatrutide-pytest")
        assert after["handle"] == "retatrutide-pytest"                    # admin field == live URL
        assert server.published_handle(after, "bg") == "retatrutide-pytest"
        assert not server.retired_handle(after, "bg", "retatrutide-pytest")
        assert server.retired_handle(after, "bg", doc["handle"])          # the old URL 404s
        assert [(r["from"], r["to"]) for r in after["rotations"]] == [(doc["handle"], "retatrutide-pytest")]
    finally:
        run(server.db.products.delete_one({"id": doc["id"]}))


def test_a_second_rename_keeps_exactly_one_live_url():
    doc = _product(f"2-tesamorelin-{uuid.uuid4().hex[:3]}")
    run(server.db.products.insert_one(doc.copy()))
    try:
        first = _rename(doc, "tesamorelin-pytest-1")
        second = _rename(first, "tesamorelin-pytest-2")
        assert server.published_handle(second, "bg") == "tesamorelin-pytest-2"
        for old in (doc["handle"], "tesamorelin-pytest-1"):
            assert server.retired_handle(second, "bg", old)
    finally:
        run(server.db.products.delete_one({"id": doc["id"]}))


def test_the_manual_order_follows_a_renamed_product():
    order = ["one", "21-retatrutide-5-tnn", "three"]
    renamed = {"handle": "retatrutide-tnn", "title": "Retatrutide",
               "rotations": [{"locale": "bg", "from": "21-retatrutide-5-tnn", "to": "retatrutide-tnn"}]}
    prods = [{"handle": "three", "title": "C"}, {"handle": "one", "title": "A"}, renamed]
    assert [p["handle"] for p in server._apply_manual_order(prods, order)] == [
        "one", "retatrutide-tnn", "three"]


def test_an_order_saved_before_a_translated_url_still_matches():
    order = ["one", "ghk-cu"]
    doc = {"handle": "ghk-cu-new", "title": "GHK-Cu", "translations": {"bg": {"handle": "ghk-cu"}}}
    assert [p["handle"] for p in server._apply_manual_order([{"handle": "one", "title": "A"}, doc], order)] == [
        "one", "ghk-cu-new"]


def test_a_half_finished_rename_is_repaired_at_boot():
    """The exact production state: the typed URL 404s, the old one is still served."""
    doc = {"id": f"drift-{uuid.uuid4().hex[:6]}", "handle": "retatrutide-pytest-tnn",
           "title": "Retatrutide", "price_eur": 99.0, "active": True,
           "translations": {"bg": {"handle": "21-retatrutide-5-pytest"}},
           "rotations": [{"locale": "bg", "from": "retatrutide-5", "to": "21-retatrutide-5-pytest"}]}
    run(server.db.products.insert_one(doc.copy()))
    try:
        assert server.retired_handle(doc, "bg", "retatrutide-pytest-tnn")      # the bug
        assert run(server.repair_handle_drift()) >= 1
        after = run(server.db.products.find_one({"id": doc["id"]}, {"_id": 0}))
        assert server.published_handle(after, "bg") == "retatrutide-pytest-tnn"
        assert not server.retired_handle(after, "bg", "retatrutide-pytest-tnn")
        assert server.retired_handle(after, "bg", "21-retatrutide-5-pytest")
    finally:
        run(server.db.products.delete_one({"id": doc["id"]}))


def test_the_repair_leaves_a_normal_rotation_alone():
    doc = {"id": f"rot-{uuid.uuid4().hex[:6]}", "handle": "ghk-cu-pytest", "title": "GHK-Cu",
           "price_eur": 49.0, "active": True,
           "translations": {"bg": {"handle": "ghk-cu-pytest-brk"}},
           "rotations": [{"locale": "bg", "from": "ghk-cu-pytest", "to": "ghk-cu-pytest-brk"}]}
    run(server.db.products.insert_one(doc.copy()))
    try:
        run(server.repair_handle_drift())
        after = run(server.db.products.find_one({"id": doc["id"]}, {"_id": 0}))
        assert server.published_handle(after, "bg") == "ghk-cu-pytest-brk"
        assert len(after["rotations"]) == 1
    finally:
        run(server.db.products.delete_one({"id": doc["id"]}))


def test_the_copy_does_not_repeat_the_page_heading():
    copy = "<h1>Всички пептиди</h1><p>Разгледайте селекция от пептиди.</p>"
    assert drop_leading_heading(copy, "Всички пептиди") == "<p>Разгледайте селекция от пептиди.</p>"


def test_a_heading_that_says_something_else_is_kept():
    copy = "<h1>Пептиди, изследвани за отслабване</h1><p>…</p>"
    assert drop_leading_heading(copy, "Отслабване") == copy

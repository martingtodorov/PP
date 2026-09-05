"""A Matrixify re-import must not wipe what the admin owns, and rotated URLs must 404 everywhere.

Production lost every product translation and the rotated handle of a product because the importer
re-created the documents from scratch — these guards keep that from coming back.
"""
import os
import pathlib

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import matrixify_import as mx            # noqa: E402
import prerender                         # noqa: E402

SRC = pathlib.Path(__file__).resolve().parent.parent / "matrixify_import.py"
SOURCE = SRC.read_text(encoding="utf-8")


def test_admin_owned_fields_are_declared():
    for field in ("translations", "rotations"):
        assert field in mx.KEEP_PRODUCT and field in mx.KEEP_COLLECTION and field in mx.KEEP_ARTICLE
    assert "active" in mx.KEEP_PRODUCT and "coa_image" in mx.KEEP_PRODUCT
    assert "product_order" in mx.KEEP_COLLECTION


def test_every_replacing_importer_snapshots_before_deleting():
    for coll in ("products", "collections_cat", "articles"):
        assert f'existing_by_handle("{coll}"' in SOURCE, coll
    # and the snapshot is merged back into the inserted document
    assert SOURCE.count("**keep") + SOURCE.count("**kept.get(") >= 3


def test_the_coa_image_survives_a_reimport():
    assert 'keep.get("coa_image")' in SOURCE and 'images.append(keep["coa_image"])' in SOURCE


def test_prerender_honours_rotated_handles():
    doc = {"rotations": [{"locale": "bg", "from": "old-handle", "to": "old-handle-abc"}]}
    assert prerender._retired(doc, "bg", "old-handle") is True
    assert prerender._retired(doc, "bg", "old-handle-abc") is False
    assert prerender._retired(doc, "en", "old-handle") is False
    assert prerender._retired({}, "bg", "old-handle") is False


def test_prerender_checks_retired_for_products_collections_and_articles():
    src = (pathlib.Path(prerender.__file__)).read_text(encoding="utf-8")
    assert src.count("_retired(doc, locale, handle)") == 3
    assert 'find_one({"locale": locale, "rotations.from": slug}' in src

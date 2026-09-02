"""The Matrixify import must give every record a meta title and description."""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from matrixify_import import meta, seo_pair  # noqa: E402

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def test_meta_reads_both_column_types():
    assert meta({"Metafield: title_tag [string]": " A "}, "title_tag") == "A"
    assert meta({"Metafield: title_tag [single_line_text_field]": "B"}, "title_tag") == "B"
    assert meta({}, "title_tag") == ""


def test_seo_falls_back_to_title_then_body():
    out = seo_pair({}, "Sermorelin", "<p>Пептид за <b>изследване</b></p>")
    assert out["seo_title"] == "Sermorelin"
    assert out["seo_description"] == "Пептид за изследване"
    assert seo_pair({}, "Bacteriostatic water", "")["seo_description"] == "Bacteriostatic water"


def test_metafield_wins_over_the_fallback():
    row = {"Metafield: title_tag [string]": "SEO title",
           "Metafield: description_tag [string]": "SEO description"}
    assert seo_pair(row, "Title", "body") == {"seo_title": "SEO title",
                                              "seo_description": "SEO description"}


@pytest.mark.parametrize("collection", ["products", "collections_cat", "articles"])
def test_imported_records_all_have_seo(collection):
    assert db[collection].count_documents({}) > 0
    assert db[collection].count_documents({"seo_title": {"$in": ["", None]}}) == 0
    assert db[collection].count_documents({"seo_description": {"$in": ["", None]}}) == 0


def test_imported_bg_pages_all_have_seo():
    assert db.pages.count_documents({"locale": "bg"}) > 0
    assert db.pages.count_documents({"locale": "bg", "seo_title": {"$in": ["", None]}}) == 0
    assert db.pages.count_documents({"locale": "bg", "seo_description": {"$in": ["", None]}}) == 0

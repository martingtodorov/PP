"""Product body headings survive the import and are restored on existing products (like purepeptide.bg)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import restore_headings as rh  # noqa: E402
from matrixify_import import clean_body  # noqa: E402

BODY = "<h1>Какво е Ретатрутид?</h1><p>Текст</p><h2>Приложение</h2><p>...</p>"


def test_products_keep_the_body_h1_and_levels():
    assert clean_body(BODY, "Ретатрутид", keep_h1=True) == BODY


def test_pages_still_drop_and_demote_the_h1():
    out = clean_body(BODY, "Ретатрутид")
    assert "<h1" not in out and out.startswith("<p>Текст</p>")


def test_bundled_export_has_a_heading_for_most_products():
    heads = rh.body_headings(rh.BUNDLED_XLSX)
    assert heads["21-retatrutide-5"] == "Какво е Ретатрутид?"
    assert len(heads) >= 20


def test_collections_have_their_own_page_heading():
    heads = rh.body_headings(rh.BUNDLED_XLSX, rh.SHEETS["collections"])
    assert heads["metabolic-studies"] == "Пептиди, изследвани за отслабване и метаболизъм"
    assert heads["2all-the-peptides-1"] == "Всички пептиди"


def test_norm_detects_an_already_present_heading():
    assert rh._norm("Какво е Ретатрутид?") in rh._norm("<h2>Какво е  Ретатрутид ?</h2><p>x</p>")
    assert rh._norm("Какво е Ретатрутид?") not in rh._norm("<p>Ретатрутид е пептид</p>")

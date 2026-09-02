"""The backend copy of the checkout copy must stay in sync with the storefront defaults."""
import io
import re
from pathlib import Path

import pytest

import ui_strings

FRONTEND = Path(__file__).resolve().parents[2] / "frontend/src/i18n/checkoutStrings.js"
LOCALES = ["bg", "en", "fr", "de", "cz", "hu", "pl", "sk", "si", "gr", "ro"]


def _block(locale: str) -> dict:
    src = io.open(FRONTEND, encoding="utf-8").read()
    body = src.split(f"  {locale}: {{", 1)[1].split("\n  },", 1)[0]
    pairs = re.findall(r'^\s{4}(\w+): "((?:[^"\\]|\\.)*)",$', body, re.M)
    return {k: v for k, v in pairs}


def test_backend_source_matches_the_frontend_bulgarian_defaults():
    assert _block("bg") == ui_strings.SOURCE_BG


def test_every_locale_ships_a_full_translation():
    keys = set(ui_strings.SOURCE_BG)
    assert len(keys) > 80
    for locale in LOCALES:
        missing = keys - set(_block(locale))
        assert not missing, f"{locale} is missing: {sorted(missing)[:5]}"


@pytest.mark.parametrize("key,placeholder", [
    ("freeShippingHint", "{amount}"),
    ("codeApplied", "{code}"),
    ("nearestTo", "{city}"),
    ("methodToOffice", "{courier}"),
])
def test_placeholders_survive_in_every_language(key, placeholder):
    for locale in LOCALES:
        assert placeholder in _block(locale)[key], f"{locale}/{key} lost {placeholder}"


def test_no_bulgarian_left_in_the_other_languages():
    cyr = re.compile(r"[\u0400-\u04FF]")
    for locale in [l for l in LOCALES if l not in ("bg",)]:
        leaked = [k for k, v in _block(locale).items() if cyr.search(v)]
        assert not leaked, f"{locale} still holds Cyrillic: {leaked}"

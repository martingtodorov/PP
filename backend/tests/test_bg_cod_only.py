"""Bulgaria is cash-on-delivery only (owner's decision, 06.2026) — no bank transfer."""
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import nextcart  # noqa: E402


def test_bg_offers_only_cod():
    keys = [m["key"] for m in nextcart.payment_methods_for("BG")]
    assert keys == ["cod"]


def test_a_bg_bank_transfer_choice_is_corrected_to_cod():
    assert nextcart.payment_method_for("BG", "bank_transfer") == "cod"


def test_prepaid_markets_are_unchanged():
    assert nextcart.payment_method_for("FR", "cod") == "bank_transfer"
    assert [m["key"] for m in nextcart.payment_methods_for("ES")] == ["bank_transfer"]


def test_markets_with_both_keep_the_customer_choice():
    assert nextcart.payment_method_for("DE", "bank_transfer") == "bank_transfer"
    assert nextcart.payment_method_for("DE", "cod") == "cod"

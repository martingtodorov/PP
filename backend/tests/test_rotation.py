"""Content rotation helpers: pasted-link parsing, URL splitting, retired handles."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402


def test_parse_link_list_splits_newlines_commas_and_glued_urls():
    text = ("https://purepeptide.bg/collections/studies-on-healing"
            "https://purepeptide.bg/collections/secretagogues\n"
            "https://purepeptide.bg/collections/melanin-i-libido , "
            "https://purepeptide.bg/collections/immunology\n"
            "https://purepeptide.bg/collections/immunology")   # duplicate is dropped
    assert server.parse_link_list(text) == [
        "https://purepeptide.bg/collections/studies-on-healing",
        "https://purepeptide.bg/collections/secretagogues",
        "https://purepeptide.bg/collections/melanin-i-libido",
        "https://purepeptide.bg/collections/immunology",
    ]


def test_parse_link_list_takes_bare_paths():
    assert server.parse_link_list("/collections/immunology\n/products/bpc-157-5") == [
        "/collections/immunology", "/products/bpc-157-5"]


def test_split_url_handles_locale_prefix_and_rejects_pages():
    assert server.split_url("https://purepeptide.bg/collections/immunology") == ("collections", "immunology")
    assert server.split_url("/en/products/bpc-157-5") == ("products", "bpc-157-5")
    assert server.split_url("/articles/tb-500") == ("articles", "tb-500")
    assert server.split_url("/pages/faq") == ("", "")
    assert server.split_url("https://purepeptide.bg/") == ("", "")


def test_rotation_code_is_three_letters_and_avoids_taken():
    code = server.rotation_code({"abc"})
    assert len(code) == 3 and code.isalpha() and code.islower() and code != "abc"


def test_retired_handle_only_for_the_rotated_locale():
    doc = {"handle": "immunology", "rotations": [{"locale": "bg", "from": "immunology", "to": "immunology-htj"}]}
    assert server.retired_handle(doc, "bg", "immunology") is True
    assert server.retired_handle(doc, "bg", "immunology-htj") is False
    assert server.retired_handle(doc, "en", "immunology") is False
    assert server.retired_handle({"handle": "x"}, "bg", "x") is False

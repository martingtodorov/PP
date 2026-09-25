"""Optional live-account tests obtain credentials privately, never from versioned literals."""
import os

import pytest


def admin_email():
    value = os.environ.get("TEST_ADMIN_EMAIL")
    if not value:
        pytest.skip("Live-account tests require private TEST_ADMIN_EMAIL", allow_module_level=True)
    return value


def admin_password():
    value = os.environ.get("TEST_ADMIN_PASSWORD")
    if not value:
        pytest.skip("Live-account tests require private TEST_ADMIN_PASSWORD", allow_module_level=True)
    return value
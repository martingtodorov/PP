"""Guards the deploy: requirements-prod.txt must be installable on a plain server."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "deploy" / "requirements-prod.txt"
DEV = ROOT / "backend" / "requirements.txt"

# packages that only exist on the Emergent package index
PLATFORM_ONLY = {"emergentintegrations"}


def _names(path: Path):
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert not line.startswith(("http://", "https://", "git+")), f"URL pin is not portable: {line}"
        name = line.split("==")[0].split(">=")[0].split("[")[0].strip().lower()
        out[name] = line
    return out


def test_prod_requirements_exists():
    assert PROD.exists(), "deploy/requirements-prod.txt is missing"


def test_no_platform_only_packages():
    names = _names(PROD)
    leaked = PLATFORM_ONLY & set(names)
    assert not leaked, f"remove from requirements-prod.txt: {leaked}"


def test_prod_covers_every_dev_package():
    dev, prod = _names(DEV), _names(PROD)
    missing = {n: v for n, v in dev.items() if n not in prod and n not in PLATFORM_ONLY}
    assert not missing, f"regenerate requirements-prod.txt, missing: {sorted(missing)}"


@pytest.mark.parametrize("module", ["server", "storage", "email_templates", "abandoned", "nextcart"])
def test_backend_modules_do_not_import_platform_packages(module):
    src = (ROOT / "backend" / f"{module}.py").read_text()
    for pkg in PLATFORM_ONLY:
        assert pkg not in src, f"{module}.py imports {pkg}, which cannot be installed on the server"


def test_no_hardcoded_admin_credentials():
    """Admin credentials must come from the environment only — the repo may end up on GitHub."""
    src = (ROOT / "backend" / "server.py").read_text()
    for var in ("ADMIN_PASSWORD", "ADMIN_EMAIL", "JWT_SECRET"):
        assert f'os.environ.get("{var}"' not in src, f"{var} must not have a default value"
        assert f'os.environ["{var}"]' in src, f"{var} must be read with os.environ[...]"

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


# import name -> distribution name on PyPI
IMPORT_TO_PACKAGE = {
    "PIL": "pillow", "anthropic": "anthropic", "bcrypt": "bcrypt", "dotenv": "python-dotenv",
    "fastapi": "fastapi", "httpx": "httpx", "jwt": "pyjwt", "motor": "motor",
    "openpyxl": "openpyxl", "pydantic": "pydantic", "pymongo": "pymongo",
    "pywebpush": "pywebpush", "requests": "requests", "resend": "resend", "starlette": "starlette",
}
# needed at runtime without being imported directly
RUNTIME_EXTRAS = {"uvicorn", "email-validator", "python-multipart"}


def _third_party_imports():
    import ast
    import sys

    local = {f.stem for f in (ROOT / "backend").glob("*.py")}
    mods = set()
    for path in (ROOT / "backend").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    return {m for m in mods if m not in sys.stdlib_module_names and m not in local}


def test_prod_covers_every_backend_import():
    prod = _names(PROD)
    missing = {}
    for mod in _third_party_imports():
        pkg = IMPORT_TO_PACKAGE.get(mod, mod).lower()
        if pkg not in prod:
            missing[mod] = pkg
    assert not missing, f"add to requirements-prod.txt: {missing}"


def test_prod_covers_the_runtime_extras():
    prod = _names(PROD)
    assert not (RUNTIME_EXTRAS - set(prod)), f"missing: {sorted(RUNTIME_EXTRAS - set(prod))}"


def test_prod_is_a_minimal_list_not_a_pip_freeze():
    """A `pip freeze` of the dev pod pins ~90 unrelated packages whose versions conflict on a modern
    Python (google-api-core needs grpcio-status>=1.75.1 on 3.14) — keep only what we import."""
    prod = _names(PROD)
    assert len(prod) <= 25, f"{len(prod)} pins — this looks like a pip freeze again"
    forbidden = {"google-api-core", "google-generativeai", "google-genai", "grpcio", "grpcio-status",
                 "litellm", "openai", "pandas", "numpy", "boto3", "botocore", "black", "mypy",
                 "pytest", "flake8", "isort", "stripe", "tokenizers", "huggingface-hub", "tiktoken"}
    leaked = forbidden & set(prod)
    assert not leaked, f"remove from requirements-prod.txt: {sorted(leaked)}"


def test_every_dependency_is_pinned():
    for name, line in _names(PROD).items():
        assert "==" in line, f"{name} is not pinned: {line}"


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

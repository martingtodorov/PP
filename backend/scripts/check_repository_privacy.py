"""Read-only publication guard for the CURRENT checkout, not a guarantee about Git history."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_PREFIXES = ("backend/data/", "backend/.media/", "backend/.image_cache/", "uploads/",
                    "backups/", "test_reports/", ".screenshots/")
PRIVATE_SUFFIXES = {".xlsx", ".xls", ".csv", ".jsonl", ".sql", ".db", ".sqlite", ".dump", ".bak", ".log"}
SAFE_MEMORY = {"memory/PRD.md", "memory/ROADMAP.md", "memory/SECRETS.md"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "provider credential": re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{24,}\b"),
    "legacy admin password": re.compile(r"Admin@PurePeptide\d+"),
    "live merchant media identifier": re.compile(r"cdn\.shopify\.com/s/files/1/\d{4}/\d{4}/\d{4}"),
}


def findings(root=ROOT):
    names = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root).decode().split("\0")
    found = []
    for name in sorted(set(names) - {""}):
        path = root / name
        if not path.is_file():
            continue  # Deleted files may remain in Git's index until the platform checkpoints them.
        parts = path.relative_to(root).parts
        private = (name.startswith(PRIVATE_PREFIXES) or path.suffix.lower() in PRIVATE_SUFFIXES
                   or name in (".gitconfig", "test_result.md")
                   or name.startswith("memory/") and name not in SAFE_MEMORY
                   or any(part == ".env" or part.startswith(".env.") for part in parts))
        if private:
            found.append((name, "private runtime artifact"))
            continue
        if ".emergent" in parts:
            continue  # Platform-owned files are not modified by this guard.
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                found.append((name, label))
    return found


if __name__ == "__main__":
    results = findings()
    for name, label in results:
        print(f"BLOCKED: {name}: {label}")  # Never print the matching value.
    print(f"Current-checkout publication findings: {len(results)}; historical commits are NOT assessed here")
    raise SystemExit(bool(results))
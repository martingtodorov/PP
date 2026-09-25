"""Keep private runtime files on their existing server when publishing code-only releases.

No database connections, remote downloads or deletions. Existing shared files always win.
"""
import argparse
import shutil
import uuid
from pathlib import Path

ASSETS = ("hero-home.png", "hero-home.webp", "og-image.jpg")


def copy_missing(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_dir() or source.resolve() == destination.resolve():
        return
    for item in source.rglob("*"):
        if not item.is_file() or item.is_symlink():
            continue
        target = destination / item.relative_to(source)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def preserve_backend(app_root, current_backend, new_backend):
    app_root, current_backend, new_backend = map(Path, (app_root, current_backend, new_backend))
    candidates = [current_backend]
    for pattern in ("releases/*/backend", "releases/*/*/backend", "releases/*"):
        candidates.extend(sorted(app_root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True))
    for relative, private_name in (("data/nextcart", "nextcart"), (".image_cache", "image-cache")):
        shared = app_root / "shared" / private_name
        shared.mkdir(parents=True, exist_ok=True)
        for old in candidates:
            if old.resolve() != new_backend.resolve() and (old / "server.py").is_file():
                copy_missing(old / relative, shared)
        destination = new_backend / relative
        if destination.is_symlink():
            if destination.resolve() != shared.resolve():
                raise ValueError("Unexpected runtime symlink; refusing to replace it")
            continue
        if destination.exists():
            copy_missing(destination, shared)
            # Preserve even an unexpected occupied target; never delete a runtime directory.
            backup = app_root / "shared" / f"adopted-{private_name}-{uuid.uuid4().hex}"
            shutil.move(str(destination), str(backup))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(shared.resolve(), target_is_directory=True)


def preserve_frontend(web_root, stage):
    web_root, stage = Path(web_root), Path(stage)
    shared = web_root / "shared" / "public-media"
    shared.mkdir(parents=True, exist_ok=True)
    stage.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        private = shared / name
        if not private.exists():
            for previous in (web_root / "build", web_root / "build.previous"):
                source = previous / name
                if source.is_file():
                    shutil.copy2(source, private)
                    break
        target = stage / name
        if private.is_file() and not target.exists():
            shutil.copy2(private, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    backend = modes.add_parser("backend")
    backend.add_argument("--app-root", required=True)
    backend.add_argument("--current-backend", required=True)
    backend.add_argument("--new-backend", required=True)
    frontend = modes.add_parser("frontend")
    frontend.add_argument("--web-root", required=True)
    frontend.add_argument("--stage", required=True)
    args = parser.parse_args()
    if args.mode == "backend":
        preserve_backend(args.app_root, args.current_backend, args.new_backend)
    else:
        preserve_frontend(args.web_root, args.stage)
    print("Server runtime files preserved without overwriting shared data")
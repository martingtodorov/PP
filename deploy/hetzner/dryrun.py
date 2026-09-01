"""Offline dry-run of the Hetzner deploy: renders every artefact and validates it with the real tools.

Not part of the pytest suite (needs nginx / systemd-analyze). Run manually:
    python deploy/hetzner/dryrun.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "deploy" / "hetzner" / "ansible"
OUT = Path("/tmp/pp-dryrun")
FAILURES = []


def ok(msg):
    print(f"  \033[32mPASS\033[0m {msg}")


def bad(msg):
    FAILURES.append(msg)
    print(f"  \033[31mFAIL\033[0m {msg}")


def render():
    v = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())
    env = Environment(loader=FileSystemLoader(str(ANSIBLE / "templates")), undefined=StrictUndefined)
    env.filters["regex_replace"] = lambda s, f, r: re.sub(f, r.replace("\\\\", "\\"), s)
    env.filters["bool"] = lambda x: str(x).lower() in ("true", "1", "yes")
    ctx = dict(v)
    ctx.update({
        "wg_front_private": "aGVsbG8=", "wg_front_public": "aGVsbG8=",
        "wg_back_private": "aGVsbG8=", "wg_back_public": "aGVsbG8=",
        "nginx_http2_directive": "http2on",
        "wg_subnet": "10.99.0.0/24",
        "ansible_distribution_release": "jammy",
        "backend_rel_path": "backend",
    })
    OUT.mkdir(parents=True, exist_ok=True)
    files = {}
    for tpl in sorted((ANSIBLE / "templates").glob("*.j2")):
        name = tpl.name[:-3]
        body = env.get_template(tpl.name).render(**ctx)
        (OUT / name).write_text(body)
        files[name] = body
    ok(f"rendered {len(files)} templates with StrictUndefined")
    return ctx, files


def check_systemd(files):
    for unit in ["purepeptide-backend.service", "pp-wg-route-guard.service", "pp-wg-route-guard.timer"]:
        p = OUT / unit
        r = subprocess.run(["systemd-analyze", "verify", str(p)], capture_output=True, text=True)
        noise = ("Unit is bound to inactive unit", "not found", "Failed to open", "does not exist",
                 "is not executable")
        errors = [l for l in (r.stderr + r.stdout).splitlines()
                  if l.strip() and not any(n in l for n in noise)]
        if errors:
            bad(f"{unit}: {errors}")
        else:
            ok(f"{unit} verified by systemd-analyze")


def check_nginx(ctx, files):
    fake = OUT / "fake"
    (fake / "build" / "static").mkdir(parents=True, exist_ok=True)
    (fake / "build" / "index.html").write_text("<html></html>")
    cert, key = fake / "origin.pem", fake / "origin.key"
    if not cert.exists():
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=purepeptide.bg", "-keyout", str(key), "-out", str(cert)],
                       capture_output=True, check=True)

    local = subprocess.run(["nginx", "-v"], capture_output=True, text=True)
    version = re.search(r"nginx/([0-9.]+)", local.stderr + local.stdout).group(1)
    wants_http2_on = tuple(int(p) for p in version.split(".")) >= (1, 25, 1)
    print(f"       (local nginx {version} → expects "
          f"{'http2 on;' if wants_http2_on else 'listen ... http2'})")

    env = Environment(loader=FileSystemLoader(str(ANSIBLE / "templates")), undefined=StrictUndefined)
    env.filters["regex_replace"] = lambda s, f, r: re.sub(f, r.replace("\\\\", "\\"), s)
    env.filters["bool"] = lambda x: str(x).lower() in ("true", "1", "yes")

    for directive, expected_ok in (("http2on", wants_http2_on), ("listen", not wants_http2_on)):
        site = env.get_template("nginx-purepeptide.conf.j2").render(
            **{**ctx, "nginx_http2_directive": directive})
        site = site.replace(ctx["ssl_cert_path"], str(cert)).replace(ctx["ssl_key_path"], str(key))
        site = site.replace(f'root {ctx["web_root"]}/build;', f'root {fake / "build"};')
        (OUT / f"site-{directive}.conf").write_text(site)
        (OUT / "nginx.conf").write_text(
            f"pid {OUT}/nginx.pid;\nerror_log {OUT}/error.log;\nevents {{}}\n"
            f"http {{\n  access_log {OUT}/access.log;\n  client_body_temp_path {OUT}/body;\n"
            f"  proxy_temp_path {OUT}/proxy;\n  fastcgi_temp_path {OUT}/fcgi;\n"
            f"  uwsgi_temp_path {OUT}/uwsgi;\n  scgi_temp_path {OUT}/scgi;\n"
            f"  include {OUT}/site-{directive}.conf;\n}}\n")
        r = subprocess.run(["nginx", "-t", "-c", str(OUT / "nginx.conf")], capture_output=True, text=True)
        passed = r.returncode == 0
        msg = f"nginx -t with '{directive}' variant → {'accepted' if passed else 'rejected'}"
        (ok if passed == expected_ok else bad)(msg + (" (as expected)" if passed == expected_ok else ""))


def check_env(files):
    rendered = files["backend.env"]
    keys = {l.split("=", 1)[0] for l in rendered.splitlines() if "=" in l and not l.startswith("#")}
    required = set()
    for py in (ROOT / "backend").glob("*.py"):
        required |= set(re.findall(r'os\.environ\[\s*[\'"]([A-Z0-9_]+)[\'"]\s*\]', py.read_text()))
    missing = required - keys
    (ok if not missing else bad)(f"backend.env covers every os.environ[...] key (missing: {sorted(missing)})")
    optional = set()
    for py in (ROOT / "backend").glob("*.py"):
        optional |= set(re.findall(r'os\.environ\.get\(\s*[\'"]([A-Z0-9_]+)[\'"]', py.read_text()))
    soft = sorted(optional - keys)
    print(f"       (optional env vars not in the template, defaults apply: {soft})")


def check_wireguard(files):
    back = files["wg0-back.conf"]
    if "Endpoint = 10.0.0.2:51820" in back and "Table = off" in back:
        ok("wg0-back.conf keeps the private endpoint and Table=off")
    else:
        bad("wg0-back.conf endpoint/table changed")
    r = subprocess.run(["bash", "-n", str(OUT / "pp-wg-routes.sh")], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("pp-wg-routes is valid bash")


def check_playbooks():
    if not shutil.which("ansible-playbook"):
        print("       (ansible-playbook not installed, skipping syntax checks)")
        return
    inv = OUT / "inventory.ini"
    inv.write_text((ANSIBLE / "inventory.ini.example").read_text())
    for pb in sorted((ANSIBLE / "playbooks").rglob("*.yml")):
        r = subprocess.run(["ansible-playbook", "-i", str(inv), "--syntax-check", str(pb)],
                           capture_output=True, text=True, cwd=str(ANSIBLE))
        (ok if r.returncode == 0 else bad)(f"syntax {pb.relative_to(ANSIBLE)}")


def check_requirements():
    req = ROOT / "deploy" / "requirements-prod.txt"
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--dry-run", "--quiet",
                        "--ignore-installed", "--report", str(OUT / "pip-report.json"),
                        "-r", str(req)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)(
        f"pip resolves every pin in requirements-prod.txt {r.stderr.strip()[-300:] if r.returncode else ''}")


if __name__ == "__main__":
    print("== templates")
    ctx, files = render()
    print("== systemd units")
    check_systemd(files)
    print("== nginx")
    check_nginx(ctx, files)
    print("== backend.env")
    check_env(files)
    print("== wireguard")
    check_wireguard(files)
    print("== ansible syntax")
    check_playbooks()
    print("== python dependencies")
    check_requirements()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} check(s) failed\033[0m")
        sys.exit(1)
    print("\033[32mall deploy artefacts validated\033[0m")

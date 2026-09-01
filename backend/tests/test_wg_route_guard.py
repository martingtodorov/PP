"""Functional test of the rendered WireGuard route-guard script (no root, no server).

Fakes the `ip` and `systemctl` binaries to check that /usr/local/sbin/pp-wg-routes
  * repairs the exact state we saw in production (wg0 up + handshaking, table 100 empty)
  * does nothing at all when the routing is already healthy (idempotent)
"""
import os
import stat
import subprocess
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "deploy" / "hetzner" / "ansible"
VARS = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())

BROKEN_ROUTES = ""  # table 100 empty — networkd wiped it
BROKEN_RULES = "0:\tfrom all lookup local\n32766:\tfrom all lookup main\n32767:\tfrom all lookup default\n"
HEALTHY_ROUTES = "default dev wg0 scope link\n"
HEALTHY_RULES = (
    "0:\tfrom all lookup local\n"
    "990:\tfrom all to 10.0.0.0/16 lookup main\n"
    "1000:\tfrom all lookup 100\n"
    "32766:\tfrom all lookup main\n"
)


def _script(tmp_path: Path) -> Path:
    env = Environment(loader=FileSystemLoader(str(ANSIBLE / "templates")))
    body = env.get_template("pp-wg-routes.sh.j2").render(**VARS)
    path = tmp_path / "pp-wg-routes"
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _fake_bin(tmp_path: Path, routes: str, rules: str) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "calls.log"
    (tmp_path / "routes.txt").write_text(routes)
    (tmp_path / "rules.txt").write_text(rules)
    (bindir / "ip").write_text(
        "#!/bin/bash\n"
        f'echo "ip $*" >> {log}\n'
        'case "$*" in\n'
        '  *"link show wg0"*) exit 0 ;;\n'
        f'  *"route show table"*) cat {tmp_path / "routes.txt"} ; exit 0 ;;\n'
        f'  *"rule show"*) cat {tmp_path / "rules.txt"} ; exit 0 ;;\n'
        'esac\n'
        "exit 0\n"
    )
    (bindir / "systemctl").write_text(f'#!/bin/bash\necho "systemctl $*" >> {log}\nexit 0\n')
    for f in bindir.iterdir():
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return log


def _run(tmp_path, routes, rules):
    script = _script(tmp_path)
    log = _fake_bin(tmp_path, routes, rules)
    env = dict(os.environ, PATH=f"{tmp_path / 'bin'}:{os.environ['PATH']}")
    proc = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return log.read_text() if log.exists() else ""


def test_guard_repairs_the_production_failure(tmp_path):
    calls = _run(tmp_path, BROKEN_ROUTES, BROKEN_RULES)
    assert "ip route replace default dev wg0 table 100" in calls
    assert "ip rule add from all lookup 100 priority 1000" in calls
    assert "ip rule add to 10.0.0.0/16 lookup main priority 990" in calls
    assert "systemctl" not in calls  # the tunnel itself is healthy, never restart it


def test_guard_is_idempotent_when_everything_is_healthy(tmp_path):
    calls = _run(tmp_path, HEALTHY_ROUTES, HEALTHY_RULES)
    assert "route replace" not in calls
    assert "rule add" not in calls

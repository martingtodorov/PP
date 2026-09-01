"""Guards the deploy config: production infrastructure must stay authoritative.

Static checks over the Ansible tree — no server access needed.
Run: python -m pytest backend/tests/test_deploy_config.py -q
"""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "deploy" / "hetzner" / "ansible"
PLAYBOOKS = ANSIBLE / "playbooks"
BOOTSTRAP = PLAYBOOKS / "bootstrap"
TEMPLATES = ANSIBLE / "templates"
TASKS = ANSIBLE / "tasks"

ROUTINE = ["preflight.yml", "site.yml", "deploy_backend.yml", "deploy_frontend.yml", "deploy_nginx.yml"]

EXAMPLE_VARS = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())


def _code_lines(text: str) -> str:
    """Drop comment lines so documentation may mention the forbidden values."""
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))


def _tasks(node):
    """Yield every task dict of a playbook / tasks file, recursing into blocks."""
    if isinstance(node, list):
        for item in node:
            yield from _tasks(item)
    elif isinstance(node, dict):
        if any(k in node for k in ("tasks", "pre_tasks", "post_tasks", "handlers", "block",
                                   "rescue", "always")):
            for key in ("tasks", "pre_tasks", "post_tasks", "handlers", "block", "rescue", "always"):
                yield from _tasks(node.get(key) or [])
            if "block" not in node:
                return
        if "import_playbook" not in node and any(
            k not in ("name", "hosts", "become", "vars", "tags", "gather_facts", "tasks",
                      "pre_tasks", "post_tasks", "handlers", "block", "rescue", "always",
                      "vars_files", "roles")
            for k in node
        ):
            yield node


def _modules(path: Path):
    doc = yaml.safe_load(path.read_text())
    mods = set()
    for task in _tasks(doc):
        for key in task:
            if key in ("name", "when", "loop", "with_items", "register", "tags", "become",
                       "become_user", "changed_when", "failed_when", "args", "notify", "vars",
                       "until", "retries", "delay", "ignore_errors", "delegate_to", "environment",
                       "check_mode", "run_once", "no_log", "listen"):
                continue
            mods.add(key.split(".")[-1])
    return mods


# ---------------------------------------------------------------- WireGuard endpoint


def test_wireguard_backend_endpoint_is_private():
    """pp-back has no public route before the tunnel — the endpoint must be the private address."""
    conf = (TEMPLATES / "wg0-back.conf.j2").read_text()
    assert "{{ wg_front_endpoint }}" in conf
    assert "2.28.79.24" not in conf
    assert EXAMPLE_VARS["wg_front_endpoint"] == "10.0.0.2:51820"


def test_no_public_ip_endpoint_anywhere():
    for path in ANSIBLE.rglob("*"):
        if path.is_file() and path.suffix in (".yml", ".j2", ".ini", ".cfg", ".example"):
            body = _code_lines(path.read_text())
            assert "2.28.79.24:51820" not in body, f"public-IP wg endpoint in {path.name}"


def test_infra_defaults_derive_the_endpoint_from_the_private_ip():
    text = (TASKS / "infra_defaults.yml").read_text()
    assert "frontend_private_ip ~ ':' ~ wg_port" in text
    assert "frontend_public_ip not in wg_front_endpoint" in text


# ---------------------------------------------------------------- routine vs bootstrap


def test_site_yml_is_application_only():
    site = yaml.safe_load((PLAYBOOKS / "site.yml").read_text())
    imported = [entry["import_playbook"] for entry in site]
    assert imported == ["preflight.yml", "deploy_backend.yml", "deploy_frontend.yml", "deploy_nginx.yml"]
    assert not any("bootstrap" in name for name in imported)


@pytest.mark.parametrize("playbook", ROUTINE)
def test_routine_playbooks_install_nothing_and_manage_no_infrastructure(playbook):
    forbidden_modules = {"apt", "apt_repository", "apt_key", "npm", "pip_install", "ufw", "sysctl",
                         "user", "group", "authorized_key", "hostname", "reboot", "yum", "dnf"}
    mods = _modules(PLAYBOOKS / playbook)
    assert not (mods & forbidden_modules), f"{playbook} uses {mods & forbidden_modules}"

    text = _code_lines((PLAYBOOKS / playbook).read_text())
    forbidden_text = [r"wg genkey", r"iptables\s+(-t\s+nat\s+)?-[AFID]\b", r"resolved\.conf",
                      r"mongodb-org", r"openssl", r"sudoers", r"self-signed",
                      r"wg-quick@wg0.*state:\s*restarted", r"nodesource"]
    for pattern in forbidden_text:
        hit = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        assert not hit, f"{playbook} must not manage infrastructure: {hit.group(0)!r}"


def test_routine_playbooks_never_rewrite_wireguard_or_tls():
    for name in ROUTINE:
        text = _code_lines((PLAYBOOKS / name).read_text())
        assert "wg0.conf" not in text, f"{name} must not touch wg0.conf"
        assert "ssl_cert_path }}" not in text or "stat" in text  # only existence checks


def test_bootstrap_playbooks_exist_and_are_separate():
    for name in ["bootstrap_frontend_base.yml", "bootstrap_nat.yml", "bootstrap_dns.yml",
                 "bootstrap_backend_base.yml", "bootstrap_firewall.yml", "bootstrap_all.yml"]:
        assert (BOOTSTRAP / name).exists(), f"missing {name}"


def test_bootstrap_all_covers_a_fresh_pair_of_servers():
    order = [e["import_playbook"] for e in yaml.safe_load((BOOTSTRAP / "bootstrap_all.yml").read_text())]
    assert order == ["bootstrap_frontend_base.yml", "bootstrap_nat.yml", "bootstrap_dns.yml",
                     "bootstrap_backend_base.yml", "bootstrap_firewall.yml"]


# ---------------------------------------------------------------- the routing bug


def test_route_guard_is_shipped():
    for name in ["pp-wg-routes.sh.j2", "pp-wg-route-guard.service.j2", "pp-wg-route-guard.timer.j2"]:
        assert (TEMPLATES / name).exists(), f"missing {name}"
    script = (TEMPLATES / "pp-wg-routes.sh.j2").read_text()
    assert "ip route replace default dev wg0 table" in script
    assert "ip rule add from all lookup" in script


def test_bootstrap_nat_installs_the_permanent_fix():
    text = (BOOTSTRAP / "bootstrap_nat.yml").read_text()
    # systemd-networkd wiping foreign routes/rules is the root cause
    assert "ManageForeignRoutes=no" in text
    assert "ManageForeignRoutingPolicyRules=no" in text
    # self healing after wg-quick start, on a timer and after every apt operation
    assert "ExecStartPost=/usr/local/sbin/pp-wg-routes" in text
    assert "pp-wg-route-guard.timer" in text
    assert "DPkg::Post-Invoke" in text


def test_backend_bootstrap_brackets_package_installs_with_a_routing_check():
    text = (BOOTSTRAP / "bootstrap_backend_base.yml").read_text()
    assert text.count("tasks/wg_route_ensure.yml") >= 4, "package stages must re-assert the routing"


def test_wg_route_ensure_is_repair_only():
    text = _code_lines((TASKS / "wg_route_ensure.yml").read_text())
    assert "wg genkey" not in text
    assert "wg0.conf" not in text
    assert "state: restarted" not in text  # never restarts a healthy tunnel
    assert "ip route replace default dev wg0 table" in text


def test_fresh_backend_can_install_wireguard_without_internet():
    """chicken-and-egg: a temporary NAT path over the private network, removed afterwards."""
    text = (BOOTSTRAP / "bootstrap_nat.yml").read_text()
    assert "ip route replace default via {{ frontend_private_ip }}" in text
    assert "ip route del default via {{ frontend_private_ip }}" in text
    assert "-s {{ private_cidr }} -o {{ frontend_public_iface }} -j MASQUERADE" in text


# ---------------------------------------------------------------- undefined variables


def test_every_play_imports_the_infra_defaults():
    for path in list(PLAYBOOKS.glob("*.yml")) + list(BOOTSTRAP.glob("*.yml")):
        doc = yaml.safe_load(path.read_text())
        plays = [p for p in doc if isinstance(p, dict) and "hosts" in p]
        if not plays:  # pure import_playbook files
            continue
        for play in plays:
            imports = yaml.dump(play.get("pre_tasks") or [])
            assert "infra_defaults.yml" in imports, f"{path.name}: play '{play.get('name')}' misses infra_defaults"


@pytest.mark.parametrize("var", ["frontend_public_ip", "ssl_cert_path", "ssl_key_path",
                                 "wg_front_endpoint", "nat_table", "nat_rule_priority",
                                 "private_cidr", "frontend_private_ip", "wg_guard_interval_sec"])
def test_preflight_variables_have_a_central_default(var):
    defaults = (TASKS / "infra_defaults.yml").read_text()
    assert re.search(rf"^\s+{var}:", defaults, re.MULTILINE), f"{var} has no default"


def test_frontend_public_ip_is_derived_from_the_inventory():
    defaults = (TASKS / "infra_defaults.yml").read_text()
    assert "groups['frontend']" in defaults
    assert "ansible_host" in defaults
    assert "frontend_public_ip | default(pp_front_inventory_ip, true)" in defaults


# ---------------------------------------------------------------- unchanged guarantees


def test_wireguard_keys_are_never_regenerated_by_default():
    text = (BOOTSTRAP / "bootstrap_nat.yml").read_text()
    assert "wg_force_regenerate_keys" in text
    assert "wg_force_rewrite_config" in text
    assert EXAMPLE_VARS["wg_force_regenerate_keys"] is False
    assert EXAMPLE_VARS["wg_force_rewrite_config"] is False


def test_tls_files_are_the_existing_cloudflare_origin_pair():
    assert EXAMPLE_VARS["ssl_cert_path"] == "/etc/ssl/cloudflare/origin.pem"
    assert EXAMPLE_VARS["ssl_key_path"] == "/etc/ssl/cloudflare/origin.key"
    nginx = (TEMPLATES / "nginx-purepeptide.conf.j2").read_text()
    assert "{{ ssl_cert_path }}" in nginx and "{{ ssl_key_path }}" in nginx


def test_inventory_matches_production():
    inv = (ANSIBLE / "inventory.ini.example").read_text()
    assert "ansible_host=2.28.79.24 ansible_user=root" in inv
    assert "ansible_host=10.0.0.3 ansible_user=deploy" in inv
    assert "-J root@2.28.79.24" in inv
    assert "backend_private_ip=10.0.0.3" in inv


def test_real_repository_url():
    assert EXAMPLE_VARS["repo_url"] == "git@github.com:martingtodorov/PP.git"
    assert EXAMPLE_VARS["ref"] == "main"


def test_admin_password_is_not_reset_by_default():
    assert EXAMPLE_VARS["admin_password_reset"] is False
    env_tpl = (TEMPLATES / "backend.env.j2").read_text()
    assert "ADMIN_PASSWORD_RESET=" in env_tpl
    server = (ROOT / "backend" / "server.py").read_text()
    assert '_env_flag("ADMIN_PASSWORD_RESET")' in server


def test_media_and_secrets_are_never_touched_by_a_deploy():
    text = (PLAYBOOKS / "deploy_backend.yml").read_text()
    assert "run_media_import" in text
    assert "state: absent" not in text
    for name in ROUTINE:
        body = _code_lines((PLAYBOOKS / name).read_text())
        assert "media_dir }}/" not in body, f"{name} writes inside the media directory"


def test_every_playbook_and_tasks_file_parses():
    for path in list(PLAYBOOKS.rglob("*.yml")) + list(TASKS.rglob("*.yml")):
        yaml.safe_load(path.read_text())


# ---------------------------------------------------------------- template rendering


def test_all_templates_render_and_the_route_script_is_valid_bash(tmp_path):
    import re as _re
    import subprocess

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined)
    env.filters["regex_replace"] = lambda s, find, repl: _re.sub(find, repl.replace("\\\\", "\\"), s)
    env.filters["bool"] = lambda v: str(v).lower() in ("true", "1", "yes")
    ctx = dict(EXAMPLE_VARS)
    ctx.update({
        "wg_front_private": "PRIV", "wg_front_public": "PUB",
        "wg_back_private": "PRIV", "wg_back_public": "PUB",
        "nginx_http2_directive": "http2on",
        "ansible_distribution_release": "jammy",
        "wg_subnet": "10.99.0.0/24",
        "wg_guard_interval_sec": 30,
        "backend_rel_path": "backend",
    })
    rendered = {}
    for tpl in TEMPLATES.glob("*.j2"):
        rendered[tpl.name] = env.get_template(tpl.name).render(**ctx)

    assert "Endpoint = 10.0.0.2:51820" in rendered["wg0-back.conf.j2"]
    assert "table 100" in rendered["pp-wg-routes.sh.j2"]

    script = tmp_path / "pp-wg-routes"
    script.write_text(rendered["pp-wg-routes.sh.j2"])
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0


# ---------------------------------------------------------------- requirements discovery


def test_requirements_path_is_discovered_not_hardcoded():
    text = (PLAYBOOKS / "deploy_backend.yml").read_text()
    assert "prod_requirements_candidates" in text
    assert "requirements: \"{{ backend_requirements }}\"" in text
    assert "release_dir }}/deploy/requirements-prod.txt\n" not in text  # no hardcoded pip path
    for candidate in ["deploy/requirements-prod.txt", "backend/requirements-prod.txt",
                      "requirements-prod.txt"]:
        assert candidate in text
    assert "No requirements file in" in text            # clear failure message
    assert "requirements-prod.generated.txt" in text    # fallback derived from backend/requirements.txt


def test_fallback_filter_reproduces_requirements_prod(tmp_path):
    """The shell fallback must produce exactly deploy/requirements-prod.txt."""
    import re as _re
    import subprocess

    playbook = (PLAYBOOKS / "deploy_backend.yml").read_text()
    pattern = _re.search(r"grep -vEi '(\^\(.*?\).*?)'", playbook).group(1)
    dev = ROOT / "backend" / "requirements.txt"
    out = subprocess.run(["grep", "-vEi", pattern.replace("{{ platform_only_packages | join(\"|\") }}",
                                                          "emergentintegrations"), str(dev)],
                         capture_output=True, text=True)
    produced = sorted(l for l in out.stdout.splitlines() if l.strip() and not l.startswith("#"))
    expected = sorted(l for l in (ROOT / "deploy" / "requirements-prod.txt").read_text().splitlines()
                      if l.strip() and not l.startswith("#"))
    assert produced == expected


# ---------------------------------------------------------------- runtime config sanity


def test_nextcart_base_url_matches_the_working_api_host():
    """client.nextcartmanager.com answers 404 — deploying it breaks couriers/checkout with 502."""
    assert EXAMPLE_VARS["nextcart_base_url"] == "https://api.nextcartmanager.com"


def test_backend_env_template_covers_every_required_env_var():
    tpl = (TEMPLATES / "backend.env.j2").read_text()
    keys = {l.split("=", 1)[0] for l in tpl.splitlines() if "=" in l and not l.startswith("#")}
    required = set()
    for py in (ROOT / "backend").glob("*.py"):
        required |= set(re.findall(r'os\.environ\[\s*[\'"]([A-Z0-9_]+)[\'"]\s*\]', py.read_text()))
    assert not (required - keys), f"backend.env.j2 misses {sorted(required - keys)}"


def test_deploy_verifies_the_public_apis_after_restart():
    text = (PLAYBOOKS / "deploy_backend.yml").read_text()
    assert "/api/nextcart/countries" in text   # couriers / checkout
    assert "/api/products?locale=bg" in text   # catalog


def test_requirements_prod_is_tracked_by_git_and_installable():
    """The deploy fails if this file is not in the pushed ref — keep it committed."""
    import subprocess

    r = subprocess.run(["git", "ls-files", "--error-unmatch", "deploy/requirements-prod.txt"],
                       cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0, "deploy/requirements-prod.txt is NOT tracked by git"
    body = (ROOT / "deploy" / "requirements-prod.txt").read_text().splitlines()
    pins = [l for l in body if l.strip() and not l.startswith("#")]
    assert len(pins) > 100
    assert all("==" in l for l in pins), "every dependency must be pinned"
    assert not any(l.lower().startswith("emergentintegrations") for l in pins)
    for pkg in ["fastapi", "uvicorn", "motor", "pymongo", "pydantic", "python-dotenv", "resend",
                "anthropic", "pillow", "pywebpush", "bcrypt"]:
        assert any(l.lower().startswith(pkg) for l in pins), f"{pkg} missing from requirements-prod.txt"


def test_deploy_backend_searches_the_whole_release_and_reports_the_tree():
    text = (PLAYBOOKS / "deploy_backend.yml").read_text()
    assert "recurse: true" in text
    assert "Top level of the checkout" in text
    assert "backend/server.py" in text  # wrong repo layout is detected immediately


def test_deploy_adapts_to_the_repository_layout():
    back = (PLAYBOOKS / "deploy_backend.yml").read_text()
    front = (PLAYBOOKS / "deploy_frontend.yml").read_text()
    unit = (TEMPLATES / "purepeptide-backend.service.j2").read_text()
    assert "backend_src_dir" in back and "backend_rel_path" in back
    assert "contains no backend/server.py" in back      # clear failure with the checkout listing
    assert "frontend_src_dir" in front and "contains no frontend/package.json" in front
    assert "{{ app_dir }}/current/{{ backend_rel_path }}" in unit
    assert "{{ release_dir }}/backend" not in back      # no hardcoded subdirectory left
    assert "{{ src_dir }}/frontend" not in front
    defaults = (TASKS / "infra_defaults.yml").read_text()
    assert "backend_rel_path: \"{{ backend_rel_path | default('backend', true) }}\"" in defaults

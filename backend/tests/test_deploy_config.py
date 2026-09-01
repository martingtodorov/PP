"""Guards the deploy config: production infrastructure must stay authoritative.

These are static checks over the Ansible tree — no server access needed.
"""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "deploy" / "hetzner" / "ansible"
PLAYBOOKS = ANSIBLE / "playbooks"
TEMPLATES = ANSIBLE / "templates"


def test_wireguard_backend_endpoint_is_private():
    """pp-back has no public route before the tunnel — the endpoint must be the private address."""
    conf = (TEMPLATES / "wg0-back.conf.j2").read_text()
    assert "{{ wg_front_endpoint }}" in conf
    assert "2.28.79.24" not in conf
    vars_file = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())
    assert vars_file["wg_front_endpoint"] == "10.0.0.2:51820"


def _code_lines(text: str) -> str:
    """Drop comment lines so documentation may mention the forbidden values."""
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))


def test_no_public_ip_endpoint_anywhere():
    for path in ANSIBLE.rglob("*"):
        if path.is_file() and path.suffix in (".yml", ".j2", ".ini", ".cfg", ".example"):
            body = _code_lines(path.read_text())
            assert "2.28.79.24:51820" not in body, f"public-IP wg endpoint in {path.name}"


def test_site_yml_is_application_only():
    site = yaml.safe_load((PLAYBOOKS / "site.yml").read_text())
    imported = [entry["import_playbook"] for entry in site]
    assert imported == ["preflight.yml", "deploy_backend.yml", "deploy_frontend.yml", "deploy_nginx.yml"]
    assert not any("bootstrap" in name for name in imported)


@pytest.mark.parametrize("playbook", ["deploy_backend.yml", "deploy_frontend.yml", "deploy_nginx.yml",
                                      "preflight.yml", "site.yml"])
def test_routine_playbooks_touch_no_infrastructure(playbook):
    text = _code_lines((PLAYBOOKS / playbook).read_text())
    # only mutating operations are forbidden — read-only verification (wg show, curl, ping) is fine
    forbidden = [
        r"^\s*-?\s*(ufw|apt|apt_repository|apt_key|sysctl|user|group|authorized_key|hostname)\s*:",
        r"wg genkey", r"iptables\s+(-t\s+nat\s+)?-[AFID]\b", r"resolved\.conf",
        r"mongodb-org", r"openssl", r"sudoers", r"self-signed",
        r"wg-quick@wg0.*state:\s*restarted",
    ]
    for pattern in forbidden:
        hit = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        assert not hit, f"{playbook} must not manage infrastructure: {hit.group(0)!r}"


def test_bootstrap_playbooks_exist_and_are_separate():
    boot = PLAYBOOKS / "bootstrap"
    for name in ["bootstrap_nat.yml", "bootstrap_dns.yml", "bootstrap_backend_base.yml",
                 "bootstrap_firewall.yml", "bootstrap_all.yml"]:
        assert (boot / name).exists(), f"missing {name}"


def test_wireguard_keys_are_never_regenerated_by_default():
    text = (PLAYBOOKS / "bootstrap" / "bootstrap_nat.yml").read_text()
    assert "wg_force_regenerate_keys" in text
    assert "wg_force_rewrite_config" in text
    vars_file = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())
    assert vars_file["wg_force_regenerate_keys"] is False
    assert vars_file["wg_force_rewrite_config"] is False


def test_tls_files_are_the_existing_cloudflare_origin_pair():
    vars_file = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())
    assert vars_file["ssl_cert_path"] == "/etc/ssl/cloudflare/origin.pem"
    assert vars_file["ssl_key_path"] == "/etc/ssl/cloudflare/origin.key"
    nginx = (TEMPLATES / "nginx-purepeptide.conf.j2").read_text()
    assert "{{ ssl_cert_path }}" in nginx and "{{ ssl_key_path }}" in nginx


def test_inventory_matches_production():
    inv = (ANSIBLE / "inventory.ini.example").read_text()
    assert "ansible_host=2.28.79.24 ansible_user=root" in inv
    assert "ansible_host=10.0.0.3 ansible_user=deploy" in inv
    assert "-J root@2.28.79.24" in inv
    assert "backend_private_ip=10.0.0.3" in inv


def test_real_repository_url():
    vars_file = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())
    assert vars_file["repo_url"] == "git@github.com:martingtodorov/PP.git"
    assert vars_file["ref"] == "main"


def test_admin_password_is_not_reset_by_default():
    vars_file = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())
    assert vars_file["admin_password_reset"] is False
    env_tpl = (TEMPLATES / "backend.env.j2").read_text()
    assert "ADMIN_PASSWORD_RESET=" in env_tpl
    server = (ROOT / "backend" / "server.py").read_text()
    assert '_env_flag("ADMIN_PASSWORD_RESET")' in server


def test_media_import_is_opt_in():
    text = (PLAYBOOKS / "deploy_backend.yml").read_text()
    assert "run_media_import" in text
    assert "media_dir" not in text.split("# ---------------- code")[0].replace("media_dir }}", "")


def test_every_playbook_parses():
    for path in PLAYBOOKS.rglob("*.yml"):
        yaml.safe_load(path.read_text())

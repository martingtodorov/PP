"""Nightly backup = database + media + env, restorable on a fresh server (deploy artefacts)."""
import re
import subprocess
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "deploy" / "hetzner" / "ansible"
TEMPLATES = ANSIBLE / "templates"
EXAMPLE_VARS = yaml.safe_load((ANSIBLE / "group_vars" / "all.yml.example").read_text())


def _render(name: str, **extra) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined)
    ctx = {**EXAMPLE_VARS, **extra}
    return env.get_template(name).render(**ctx)


def test_backup_script_covers_db_media_and_env_and_is_valid_bash(tmp_path):
    script = _render("pp-backup.sh.j2")
    assert 'mongodump --db "$DB"' in script and 'DB="purepeptide"' in script
    assert 'tar -C "$MEDIA_DIR" -czf' in script and "/var/lib/purepeptide/media" in script
    assert "backend.env" in script
    assert "gzip -t" in script and "tar -tzf" in script, "archives must be verified"
    assert "-mtime +\"$KEEP_DAYS\"" in script and 'KEEP_DAYS="14"' in script
    assert "rsync" in script and 'OFFSITE=""' in script
    path = tmp_path / "pp-backup"
    path.write_text(script)
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0


def test_restore_script_restores_both_and_asks_before_wiping(tmp_path):
    script = _render("pp-restore.sh.j2")
    assert "mongorestore --drop" in script
    assert 'tar -C "$MEDIA_DIR" -xzf' in script
    assert "systemctl stop" in script and "systemctl start" in script
    assert "read -r -p" in script and "--yes" in script
    assert "chown -R" in script and "www-data" in script
    path = tmp_path / "pp-restore"
    path.write_text(script)
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0


def test_backup_tasks_are_installed_by_bootstrap_and_by_every_deploy():
    tasks = yaml.safe_load((ANSIBLE / "tasks" / "backup.yml").read_text())
    names = " ".join(t["name"] for t in tasks)
    assert "pp-backup" in names and "pp-restore" in names
    cron = next(t for t in tasks if "cron" in t)
    assert cron["cron"]["name"] == "{{ app_name }} mongodump", "must replace the old mongodump-only entry"
    assert cron["cron"]["job"].startswith("/usr/local/sbin/pp-backup")
    for playbook in ("deploy_backend.yml", "bootstrap/bootstrap_backend_base.yml"):
        text = (ANSIBLE / "playbooks" / playbook).read_text()
        assert re.search(r"import_tasks: \.\./(?:\.\./)?tasks/backup\.yml", text), playbook
        assert "mongodump --db" not in text, f"{playbook} keeps an old inline dump job"


def test_backup_defaults_exist_centrally():
    defaults = (ANSIBLE / "tasks" / "infra_defaults.yml").read_text()
    for var in ("backup_dir", "backup_keep_days", "backup_offsite"):
        assert var in defaults and var in EXAMPLE_VARS

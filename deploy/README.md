# PurePeptide — deploy

Everything needed to run the shop on our own hardware (Hetzner, no Docker: systemd + venv + nginx).

* `hetzner/ansible/` — the playbooks (see `hetzner/README.md` for the full walkthrough)
* `requirements-prod.txt` — the portable Python dependency list used on the server
  (regenerate with `grep -v '^emergentintegrations' backend/requirements.txt > deploy/requirements-prod.txt`
  and verify with `pytest backend/tests/test_requirements_portable.py`)

## Topology

| Host | Address | Runs |
|---|---|---|
| `pp-front` | `2.28.79.24` public, `10.0.0.2` private, `eth0` | nginx, TLS, the static build, WireGuard NAT gateway |
| `pp-back` | `10.0.0.3` private only, `enp7s0` | FastAPI on `:8001`, MongoDB on `127.0.0.1:27017`, media disk |

**The running production infrastructure is authoritative.** `playbooks/site.yml` deploys application code
only; everything that provisions infrastructure lives in `playbooks/bootstrap/` and is human-triggered.

`pp-back` has no public IPv4 and reaches the internet through `pp-front` over a WireGuard tunnel whose
backend peer endpoint is the **private** address `10.0.0.2:51820` (never `2.28.79.24:51820` — pp-back has no
public route before the tunnel exists). Everything public sits behind Cloudflare (Full strict) with the
Origin certificate at `/etc/ssl/cloudflare/origin.{pem,key}` on `pp-front`.

```bash
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes root@2.28.79.24                    # pp-front
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -J root@2.28.79.24 deploy@10.0.0.3 # pp-back
```

## Domains

One build serves every domain; the locale is derived from the hostname by the app:

| Domain | Locale |
|---|---|
| `purepeptide.bg` | bg (canonical) |
| `purepeptide.eu` | en / fr / de / cz / hu / pl / sk / si (path prefixes) |
| `purepeptide.ro` | ro |
| `purepeptide.gr` | gr |
| `purepeptide-labs.bg` | bg (alias) |

## Environment variables that stop the boot

`MONGO_URL`, `DB_NAME`, `MEDIA_ROOT` are read at import time — if one is missing, uvicorn dies before
binding `:8001`. They live in `/etc/purepeptide/backend.env` (0640 root:www-data).

## Hard rules (each one has broken a deploy before)

0. **Never re-provision infrastructure during a deploy.** `site.yml` must not touch WireGuard, DNS,
   users, SSH keys, the firewall, TLS files, MongoDB installation, the media disk or any secret. See
   `hetzner/README.md` for the full "never does" list.
1. **One uvicorn worker.** The abandoned-cart sweeper and the AI bulk-translation jobs run in-process —
   two workers means two sweepers and duplicate recovery emails.
2. **`/var/lib/purepeptide/media` is never touched by a deploy.** With `ProtectSystem=strict` it must be
   listed in `ReadWritePaths`. All product/content images live there and are served as WebP/JPEG by the API.
3. **`REACT_APP_BACKEND_URL` must be EMPTY at build time.** CRA bakes it in; empty means same origin, which
   is what lets a single build serve all five domains. `REACT_APP_SITE_URL=https://purepeptide.bg` is used
   for sitemap/robots/OG.
4. **`proxy_buffering off` on `/api/`** — translation progress and checkout polling need unbuffered responses.
5. **HTTPS is mandatory** — secure cookies, the 90-day checkout memory and web push all depend on the origin.
6. **`requirements-prod.txt` must stay installable off-platform** — no `emergentintegrations`, no URL pins.
   Run `pytest backend/tests/test_requirements_portable.py` before every deploy.
7. **Emails only leave** after the sending domain is verified in Resend and `SENDER_EMAIL` /
   `ADMIN_NOTIFY_EMAIL` are set. Until then Resend accepts only the account owner's address.
8. **nginx HTTP/2 syntax depends on the version** — the playbook reads `nginx -v` and picks
   `listen 443 ssl http2;` or `http2 on;`.
9. **Media export runs once** (`--tags media`): `export_media_to_disk.py` pulls every file recorded in the
   `files` collection onto the local disk. It needs `EMERGENT_LLM_KEY` only for that first run; afterwards
   the site is fully self-hosted.

## Verify and rollback

```bash
curl -s localhost:8001/api/                       # on pp-back
pgrep -fc 'uvicorn server:app'                    # must be 1
runuser -u www-data -- curl -sS https://ifconfig.me   # must print pp-front's public IP (NAT works)
curl -s https://purepeptide.bg/api/nextcart/countries
curl -sI https://purepeptide.bg/api/files/<path> -H 'Accept: image/webp'   # content-type: image/webp

# rollback
sudo ln -sfn "$(readlink /opt/purepeptide/previous)" /opt/purepeptide/current \
  && sudo systemctl restart purepeptide-backend
ln -sfn "$(readlink /var/www/purepeptide/build.previous)" /var/www/purepeptide/build
```

Logs: `journalctl -fu purepeptide-backend`, `journalctl -fu nginx`, `journalctl -fu mongod`.

## Secrets and GitHub

Nothing secret is committed: `.env`, `deploy/hetzner/ansible/inventory.ini`,
`group_vars/all.yml` (vault-encrypted anyway), `memory/test_credentials.md` and `backend/.media/` are all
gitignored, and a full history scan finds no Anthropic / Resend / RevOrder key, no `.pem` and no SSH key.

Two things to keep in mind:

1. `ADMIN_EMAIL`, `ADMIN_PASSWORD` and `JWT_SECRET` have **no defaults** — the backend refuses to boot
   without them (guarded by `backend/tests/test_requirements_portable.py`).
2. The development test suite and the older `test_reports/*.json` still contain the preview admin password,
   so **set a fresh `ADMIN_PASSWORD` in the vault before going live**. `test_reports/` is now gitignored.

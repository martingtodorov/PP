# Hetzner — production is authoritative

**The running servers are the source of truth.** A normal deployment ships application code only.
Infrastructure (WireGuard/NAT, DNS, MongoDB, users, SSH keys, firewall, TLS files, secrets) is never
re-provisioned unless a human explicitly runs a `bootstrap/` playbook.

## Production state (do not change)

| | pp-front | pp-back |
|---|---|---|
| public IPv4 | `2.28.79.24` | none |
| private IPv4 | `10.0.0.2` | `10.0.0.3` |
| interface | `eth0` (public, NAT) | `enp7s0` (private) |
| SSH user | `root` | `deploy` (passwordless sudo) |
| runs | nginx, TLS, SPA build, WireGuard gateway | FastAPI :8001, MongoDB @127.0.0.1, media disk |

```bash
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes root@2.28.79.24
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -J root@2.28.79.24 deploy@10.0.0.3
```

WireGuard: `pp-front wg0 = 10.99.0.1`, `pp-back wg0 = 10.99.0.2`, listen port `51820`.

> **The backend peer endpoint is `10.0.0.2:51820` — the PRIVATE address.**
> `2.28.79.24:51820` cannot work: pp-back has no public route *before* the tunnel exists, so using the
> public IP as the endpoint deadlocks the tunnel. `wg_front_endpoint` in `group_vars` holds this value and
> `bootstrap_nat.yml` asserts it (in check mode) instead of rewriting the file.

Traffic path: `pp-back 10.0.0.3 → wg0 10.99.0.2 → 10.0.0.2:51820 → pp-front wg0 10.99.0.1 → MASQUERADE via eth0 → internet as 2.28.79.24`.

DNS on pp-back: `/etc/systemd/resolved.conf.d/pp.conf` (`DNS=1.1.1.1 8.8.8.8`, `FallbackDNS=9.9.9.9`),
systemd-resolved stays enabled, `/etc/resolv.conf` is never replaced.

TLS on pp-front: Cloudflare Origin certificate at `/etc/ssl/cloudflare/origin.pem` (0644) and
`/etc/ssl/cloudflare/origin.key` (0600), Cloudflare SSL mode **Full (strict)**. The playbooks only check
that both files exist — they never generate, replace or chmod them.

Repository: `git@github.com:martingtodorov/PP.git`, ref `main`.

## Layout of the playbooks

```
playbooks/
  site.yml                 ROUTINE DEPLOY: preflight -> backend -> frontend -> nginx
  preflight.yml            read-only infrastructure checks
  deploy_backend.yml       git checkout, pip, backend.env, systemd unit, symlink swap
  deploy_frontend.yml      yarn build + web root swap
  deploy_nginx.yml         renders the site config, reloads nginx
  bootstrap/               NEVER imported by site.yml — human-triggered only
    bootstrap_nat.yml          WireGuard + NAT (reuses existing keys and config)
    bootstrap_dns.yml          systemd-resolved drop-in
    bootstrap_backend_base.yml packages, MongoDB, directory layout, media dir, backups
    bootstrap_firewall.yml     ufw on pp-front
    bootstrap_all.yml          all of the above (new servers only)
```

## Routine deploy

```bash
cd deploy/hetzner/ansible
cp inventory.ini.example inventory.ini            # values already match production
cp group_vars/all.yml.example group_vars/all.yml  # fill in the REAL secrets, then encrypt
ansible-vault encrypt group_vars/all.yml

ansible all -i inventory.ini -m ping              # both hosts must answer SUCCESS
ansible-playbook -i inventory.ini playbooks/site.yml -e "ref=main" --ask-vault-pass
```

`preflight.yml` runs first and aborts the deploy unless:

* both hosts answer `ping`
* `wg show wg0` on pp-back has a handshake newer than 5 minutes
* `ping -c 3 1.1.1.1` works from pp-back
* `resolvectl query ifconfig.me` resolves
* `curl https://ifconfig.me` from pp-back returns `2.28.79.24`
* the Cloudflare Origin cert and key exist on pp-front and `nginx -v` works

Useful subsets:

```bash
# env change + restart only
ansible-playbook -i inventory.ini playbooks/deploy_backend.yml --tags config,service --ask-vault-pass
# nginx only
ansible-playbook -i inventory.ini playbooks/deploy_nginx.yml --tags config --ask-vault-pass
# one-off media import from the managed storage (never automatic)
ansible-playbook -i inventory.ini playbooks/deploy_backend.yml --tags media -e run_media_import=true --ask-vault-pass
```

## What a routine deploy never does

recreate servers · change any IP or the private network · touch `enp7s0`/`eth0` · create or modify Linux
users · touch `authorized_keys` or `/etc/sudoers.d/deploy` · regenerate WireGuard keys · rewrite
`wg0.conf` · use `2.28.79.24:51820` · flush iptables/NAT · install or reconfigure MongoDB · touch the
firewall · remove the DNS drop-in · generate or overwrite TLS files · reset the JWT secret, the admin
password, VAPID keys or any API key · copy `.example` files over real config · touch
`/var/lib/purepeptide/media` or the database.

Two safety switches exist and both default to `false`:
`wg_force_regenerate_keys`, `wg_force_rewrite_config`.
The admin password is only re-synced from the env when `admin_password_reset: true`.

## Paths on the hosts

```
/opt/purepeptide/releases/<ref>-<stamp>     one directory per deploy
/opt/purepeptide/current -> release         live (previous -> the one before)
/opt/purepeptide/venv                      python environment
/etc/purepeptide/backend.env                0640 root:www-data (backed up on every render)
/var/lib/purepeptide/media                  PERSISTENT images
/var/www/purepeptide/build                  SPA (build.previous = rollback)
/etc/ssl/cloudflare/origin.{pem,key}        Cloudflare Origin, managed by hand
/var/backups/purepeptide                    nightly mongodump, 14 days
```

## Rollback

```bash
sudo ln -sfn "$(readlink /opt/purepeptide/previous)" /opt/purepeptide/current \
  && sudo systemctl restart purepeptide-backend
ln -sfn "$(readlink /var/www/purepeptide/build.previous)" /var/www/purepeptide/build
```

Logs: `journalctl -fu purepeptide-backend`, `journalctl -fu nginx`, `journalctl -fu mongod`,
`sudo wg show`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| pp-back has no internet | wg endpoint changed to the public IP, or `wg-quick@wg0` down |
| `pip install` hangs on pp-back | tunnel MTU — must stay `1370` |
| uvicorn dies instantly | `MONGO_URL`, `DB_NAME` or `MEDIA_ROOT` missing from `backend.env` |
| duplicate abandoned-cart emails | more than one uvicorn worker |
| images 404 | media disk empty (`--tags media -e run_media_import=true`) or `MEDIA_ROOT` not in `ReadWritePaths` |
| API calls go to the wrong host | the SPA was built with a non-empty `REACT_APP_BACKEND_URL` |
| admin password reverted | `admin_password_reset` was set to `true` |

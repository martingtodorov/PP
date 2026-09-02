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
tasks/
  infra_defaults.yml       central non-secret defaults, imported by EVERY play
                           (frontend_public_ip is derived from the inventory, TLS paths, wg vars…)
  wg_route_ensure.yml      idempotent repair of the wg0 policy routing (see below)
playbooks/
  site.yml                 ROUTINE DEPLOY: preflight -> backend -> frontend -> nginx
  preflight.yml            infrastructure checks + wg routing repair (nothing else changes)
  deploy_backend.yml       git checkout, pip, backend.env, systemd unit, symlink swap
  deploy_frontend.yml      yarn build + web root swap (installs nothing)
  deploy_nginx.yml         renders the site config, reloads nginx
  selftest_defaults.yml    local, offline check that no variable is undefined
  bootstrap/               NEVER imported by site.yml — human-triggered only
    bootstrap_frontend_base.yml nginx + Node/yarn toolchain + web root + TLS dir
    bootstrap_nat.yml           WireGuard + NAT + the permanent route guard
    bootstrap_dns.yml           systemd-resolved drop-in
    bootstrap_backend_base.yml  packages, MongoDB, directory layout, media dir, backups
    bootstrap_firewall.yml      ufw on pp-front
    bootstrap_all.yml           the whole fresh-server sequence
```

## The disappearing WireGuard routing (fixed)

Symptom: `wg show` is perfect (recent handshake, traffic counters growing) but pp-back answers
`ping 1.1.1.1` with **Network is unreachable** and every DNS lookup fails. `ip route` shows only the
Hetzner private routes — `table 100` and the `ip rule` entries are gone.

Cause: **systemd-networkd deletes routes and routing-policy rules it does not manage**
(`ManageForeignRoutes` and `ManageForeignRoutingPolicyRules` default to `yes`). Any networkd reload —
`netplan apply`, a package install that touches the network stack, a DHCP renewal, cloud-init — wipes
what `wg-quick` added in `PostUp`, while the interface itself survives. That is why `apt` in
`bootstrap_backend_base.yml` used to kill connectivity mid-run and why DNS "broke" although the
resolver config was correct.

`bootstrap_nat.yml` now installs four layers of protection on pp-back:

1. `/etc/systemd/networkd.conf.d/10-pp-keep-foreign-routes.conf` → `ManageForeignRoutes=no`,
   `ManageForeignRoutingPolicyRules=no`
2. `/usr/local/sbin/pp-wg-routes` — idempotent restore of `default dev wg0 table 100` plus both
   `ip rule` entries
3. `pp-wg-route-guard.timer` (every 30 s) **and** a `wg-quick@wg0` drop-in
   (`ExecStartPost=/usr/local/sbin/pp-wg-routes`)
4. `/etc/apt/apt.conf.d/99-pp-wg-routes` → `DPkg::Post-Invoke` runs the script after every package
   operation

In addition, `tasks/wg_route_ensure.yml` repairs the routing in-band: it runs in `preflight.yml`,
in `deploy_backend.yml` and around every package stage of the bootstrap playbooks. Nobody has to run
`systemctl restart wg-quick@wg0` before a deploy any more.

## Fresh servers (chicken-and-egg solved)

A brand new pp-back has no internet at all, so it cannot `apt install wireguard`. `bootstrap_nat.yml`
therefore: adds a temporary `MASQUERADE` for `10.0.0.0/16` on pp-front, points pp-back's default route
at `10.0.0.2` over `enp7s0`, installs `wireguard`, brings the tunnel up, installs the route guard and
then removes both the temporary route and the temporary NAT rules. Keep the temporary NAT with
`-e keep_private_nat=true` if you want it for debugging.

```bash
cd deploy/hetzner/ansible
ansible-galaxy install -r requirements.yml          # once per workstation
cp inventory.ini.example inventory.ini
cp group_vars/all.yml.example group_vars/all.yml    # real secrets, then: ansible-vault encrypt …
ansible-playbook -i inventory.ini playbooks/bootstrap/bootstrap_all.yml --ask-vault-pass
# upload the Cloudflare Origin cert/key to /etc/ssl/cloudflare/ (0644 / 0600)
ansible-playbook -i inventory.ini playbooks/site.yml -e "ref=main" --ask-vault-pass
```

On the **existing** production pair, run `bootstrap_nat.yml` once to install the route guard
(idempotent: keys are reused, `wg0.conf` is not rewritten):

```bash
ansible-playbook -i inventory.ini playbooks/bootstrap/bootstrap_nat.yml --ask-vault-pass
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

Once bootstrapped, every later deploy is exactly this — **no local file edits, no `git stash`, no
manual route or WireGuard commands, no `apt install nginx`**:

```bash
git pull
cd deploy/hetzner/ansible
ansible-playbook -i inventory.ini playbooks/preflight.yml --ask-vault-pass
ansible-playbook -i inventory.ini playbooks/site.yml -e "ref=main" --ask-vault-pass
```

`inventory.ini`, `group_vars/all.yml` and the vault password stay on the workstation and are
gitignored, so `git pull` can never conflict with them. Every variable the playbooks use has a
default in `tasks/infra_defaults.yml`, so an older `group_vars/all.yml` cannot break a run —
verify offline with:

```bash
ansible-playbook -i inventory.ini playbooks/selftest_defaults.yml -e ansible_connection=local
```

`preflight.yml` runs first and aborts the deploy unless:

* both hosts answer `ping`
* `wg show wg0` on pp-back has a handshake newer than 5 minutes
* the wg0 policy routing exists — if networkd wiped it, preflight puts it back (the only repair it does)
* `ping -c 2 1.1.1.1` works from pp-back
* `resolvectl query ifconfig.me` resolves
* `curl https://ifconfig.me` from pp-back returns the pp-front IP **from the inventory**
* `/opt/purepeptide`, `/etc/purepeptide` and `/var/lib/purepeptide/media` exist
* the Cloudflare Origin cert and key exist on pp-front and `nginx -v`, `node -v`, `yarn -v` work
  (otherwise it prints the exact `bootstrap_frontend_base.yml` command)

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
/var/backups/purepeptide                    nightly backup: mongodump + media tar + backend.env, 14 days
```

## Backups (database + pictures together)

`/usr/local/sbin/pp-backup` runs every night at 03:20 (cron, installed by `deploy_backend.yml` and the
bootstrap). One run produces `<db>-<day>.gz` (mongodump), `media-<day>.tar.gz` (the whole
`/var/lib/purepeptide/media`) and `backend.env-<day>`; both archives are integrity-checked and
`latest-db.gz` / `latest-media.tar.gz` always point at the newest pair. Retention: `backup_keep_days`.
Set `backup_offsite` (an rsync target such as a Hetzner Storage Box) to mirror the directory off the
server after every run.

```bash
sudo pp-backup                                   # run one now
tail /var/backups/purepeptide/backup.log
ansible-playbook -i inventory.ini playbooks/deploy_backend.yml --tags backup -e run_backup_now=true --ask-vault-pass
sudo pp-restore                                  # list the available days
sudo pp-restore 2026-06-30                       # database AND media back to that night (asks for confirmation)
```

New server: bootstrap it, copy `<db>-<day>.gz` + `media-<day>.tar.gz` into `/var/backups/purepeptide`,
run `deploy_backend.yml`, then `sudo pp-restore <day>` — the site comes back with every picture.

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
| `wg show` healthy but `ping 1.1.1.1` = *Network is unreachable* | networkd wiped `table 100` / the `ip rules`. Fixed permanently by `bootstrap_nat.yml`; instant repair: `sudo /usr/local/sbin/pp-wg-routes` or re-run `preflight.yml` |
| DNS fails on pp-back | almost always the same routing problem — 1.1.1.1 is only reachable through wg0. Check the routing first, not the resolver |
| pp-back has no internet | wg endpoint changed to the public IP, or `wg-quick@wg0` down |
| `apt` on pp-back dies with *Temporary failure in name resolution* | route guard not installed → run `bootstrap_nat.yml` once |
| `Could not open requirements file: .../deploy/requirements-prod.txt` | the checked-out ref does not contain that file. `deploy_backend.yml` now searches `deploy/requirements-prod.txt`, `backend/requirements-prod.txt`, `requirements-prod.txt`, `deploy/hetzner/requirements-prod.txt` and, as a last resort, derives a portable list from `backend/requirements.txt` (minus `emergentintegrations`) into `/etc/purepeptide/requirements-prod.generated.txt` |
| `couldn't resolve module/action 'ufw'` | `ansible-galaxy install -r requirements.yml` |
| `pip install` hangs on pp-back | tunnel MTU — must stay `1370` |
| uvicorn dies instantly | `MONGO_URL`, `DB_NAME` or `MEDIA_ROOT` missing from `backend.env` |
| duplicate abandoned-cart emails | more than one uvicorn worker |
| images 404 | media disk empty (`--tags media -e run_media_import=true`) or `MEDIA_ROOT` not in `ReadWritePaths` |
| API calls go to the wrong host | the SPA was built with a non-empty `REACT_APP_BACKEND_URL` |
| admin password reverted | `admin_password_reset` was set to `true` |

# Hetzner deploy — step by step

## 0. Prerequisites

```bash
cd deploy/hetzner/ansible
ansible-galaxy collection install community.general ansible.posix
cp inventory.ini.example inventory.ini
cp group_vars/all.yml.example group_vars/all.yml
# fill in the secrets, then:
ansible-vault encrypt group_vars/all.yml
```

Upload the Cloudflare Origin certificate by hand (never in git):

```bash
ssh root@2.28.79.24 'mkdir -p /etc/ssl/purepeptide && chmod 700 /etc/ssl/purepeptide'
scp cert.pem key.pem root@2.28.79.24:/etc/ssl/purepeptide/
ssh root@2.28.79.24 'chmod 600 /etc/ssl/purepeptide/*.pem'
```

Cloudflare: SSL/TLS mode **Full (Strict)**, proxied `A` records for all five domains pointing at
`2.28.79.24`, and "Always Use HTTPS" on.

## 1. Tunnel / NAT (once)

```bash
ansible-playbook -i inventory.ini playbooks/deploy_nat.yml --ask-vault-pass
```

The playbook generates both WireGuard key pairs on `pp-front`, renders `wg0` on both hosts and prints the
public IP that `pp-back` exits through — it must equal `2.28.79.24`.

**Why WireGuard and not `ip route add default via 10.0.0.2`?** Hetzner's private network does not forward
packets whose source is a private address to the internet unless the gateway masquerades them, and the
plain-route variant breaks as soon as the private NIC name or subnet changes (and silently drops MTU-sized
packets, which made `pip install` and the courier API hang). The tunnel gives us a stable `wg0` interface, a
fixed MTU (1370) and policy routing that keeps `10.0.0.0/16` on the main table, so Ansible's jump-host
access keeps working even while the default route goes through the tunnel.

## 2. Deploy

```bash
ansible-playbook -i inventory.ini playbooks/deploy_backend.yml  -e "ref=main" --ask-vault-pass
ansible-playbook -i inventory.ini playbooks/deploy_frontend.yml -e "ref=main" --ask-vault-pass
ansible-playbook -i inventory.ini playbooks/deploy_nginx.yml    -e "ref=main" --ask-vault-pass
# or everything at once
ansible-playbook -i inventory.ini playbooks/site.yml -e "ref=main" --ask-vault-pass
```

Tags: `base, mongo, code, build, config, service, publish, media, firewall, backup, gateway, client, verify`.

Common shortcuts:

```bash
# only an env change + restart
ansible-playbook -i inventory.ini playbooks/deploy_backend.yml --tags config,service --ask-vault-pass
# re-run the media export after adding images on the platform
ansible-playbook -i inventory.ini playbooks/deploy_backend.yml --tags media --ask-vault-pass
# nginx only
ansible-playbook -i inventory.ini playbooks/deploy_nginx.yml --tags config --ask-vault-pass
```

## 3. Paths on the hosts

```
/opt/purepeptide/releases/<ref>-<stamp>     one directory per deploy
/opt/purepeptide/current -> release         live release (previous -> the one before)
/opt/purepeptide/venv                      python environment
/etc/purepeptide/backend.env                0640 root:www-data
/var/lib/purepeptide/media                  PERSISTENT image storage
/var/www/purepeptide/build                  SPA (build.previous = rollback)
/etc/ssl/purepeptide/{cert,key}.pem
/var/backups/purepeptide                    nightly mongodump, 14 days
```

## 4. First run checklist

1. `--tags media` finished and `/var/lib/purepeptide/media` is ~14 MB or more.
2. `curl -s localhost:8001/api/` on `pp-back` answers `{"service": "PurePeptide API", ...}`.
3. `pgrep -fc 'uvicorn server:app'` prints `1`.
4. Admin login works at `https://purepeptide.bg/admin/login` with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
5. Resend: the sending domain is verified, then send a test from
   Admin → Настройки → тестов имейл.
6. Web push: `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` set, then subscribe from the admin
   panel and place a test order.
7. Place one real test order per domain (BG / RO / GR / EU) and confirm the courier list and the
   confirmation email language.

## 5. Troubleshooting

| Symptom | Cause |
|---|---|
| uvicorn dies instantly | one of `MONGO_URL`, `DB_NAME`, `MEDIA_ROOT` missing from `backend.env` |
| duplicate abandoned-cart emails | more than one uvicorn worker |
| images 404 | media export not run, or `MEDIA_ROOT` not in `ReadWritePaths` |
| API calls hit the wrong host in the browser | the build was made with a non-empty `REACT_APP_BACKEND_URL` |
| `pip install` hangs on `pp-back` | tunnel MTU — check `wg_mtu: 1370` |
| 502 from nginx | backend service down (`journalctl -fu purepeptide-backend`) or wrong `backend_private_ip` |
| courier lists empty | `NEXTCART_*` variables missing, or the outbound NAT is down |

# Cloudflare Bot Fight Mode — изключи го (403 за датацентър IP-та)

**Симптом (25.09.2026):** заявки от датацентър IP-та към `purepeptide.bg` получават **403**.
Не идва от нашия сървър: гео-блокът в `nginx-purepeptide.conf.j2` е изключен
(`blocked_countries: []`) и единственото 403 правило зависи от него. Origin-ът връща 200 за `/`,
`/robots.txt`, `/sitemap*.xml`, `/api/*`, `/llms.txt`, `/agents.md` с всякакъв User-Agent.

Причината е **Cloudflare → Security → Bots → Bot Fight Mode**. То блокира заявки от известни
хостинг/датацентър ASN-и още на ръба на Cloudflare, преди да стигнат до nginx.

## Защо трябва да се изключи

- Няма изключения: Bot Fight Mode (безплатният вариант) се прилага за цялата зона и **не може** да
  бъде заобиколено с WAF Skip правило. Само платеното *Super* Bot Fight Mode е конфигурируемо.
- Блокира легитимен трафик, който не е във „verified bots" списъка на Cloudflare: SEO краулъри,
  Search Console инструменти през трети страни, PageSpeed/Lighthouse доставчици, нашият мониторинг,
  платежни/куриерски webhook-ове, които идват от облачни IP-та.
- Добавя JS challenge и на нормални посетители зад корпоративни прокси/VPN.

## Как се изключва

Cloudflare dashboard → избираш зоната (`purepeptide.bg`, после същото за `.eu`, `.ro`, `.gr`,
`purepeptide-labs.bg`) → **Security → Bots** → **Bot Fight Mode: Off**.

## Какво да сложиш вместо него

1. **WAF Rate limiting** за чувствителните точки:
   `/api/auth/login`, `/api/checkout`, `/api/orders/track` — напр. 10 заявки/минута на IP.
2. **Managed Challenge** само за `/admin*` (WAF Custom rule, действие Managed Challenge).
3 . **Не** блокирай `/robots.txt`, `/sitemap*.xml`, `/llms.txt`, `/agents.md`, `/wp-json/*`
   (NextLevel чете поръчките оттам) и `/api/*` за GET.

## Проверка след промяната

```bash
for u in / /robots.txt /sitemap.xml /api/settings; do
  curl -s -o /dev/null -w "$u %{http_code}\n" "https://purepeptide.bg$u"
done
```
Всичко трябва да е 200 (`/api/settings` също 200, HEAD дава 405 — това е нормално).

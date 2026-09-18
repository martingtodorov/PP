# Блокиране на държави (САЩ и Канада)

Решение на собственика (17.06.2026): посетител от **САЩ или Канада** не вижда магазина, а страница
„този домейн не е конфигуриран“ — така изглежда като домейн, който сочи към сървър без сайт.

## Как работи

Cloudflare подава държавата в заглавката `CF-IPCountry`, а nginx решава на входа:

```
map $http_cf_ipcountry $pp_geo_blocked { default 0; US 1; CA 1; }   # от blocked_countries
map $http_user_agent   $pp_crawler     { … googlebot|bingbot|gptbot … }
map "$pp_geo_blocked:$pp_crawler" $pp_block { default 0; "1:0" 1; }
```

`if ($pp_block) { return 403; }` стои в локациите, които отдават съдържание (`/`, `= /`, `/api/`,
`/api/files/`), а `error_page 403 /_not-live.html` подменя тялото със нашата страница
(`deploy/hetzner/ansible/files/error-pages/_not-live.html`, инсталира се в
`{{ web_root }}/error-pages/` от `deploy_nginx.yml`).

Защо `if`-ът е в локациите, а не в `server` блока: при `return 403` направо в `server`, nginx
отговаря със собствената си 403 страница и **игнорира** `error_page`.

### Кой НЕ се блокира

| Изключение | Причина |
| :--------- | :------ |
| Googlebot, Bingbot, Applebot, Yandex, GPTBot, ClaudeBot, PerplexityBot, социалните ботове, мониторингът | всички обхождат от американски IP-та — без това изключение спира индексирането в Google и Search Console спира да чете sitemap-ите |
| `/wp-json/…` | интеграционната точка, по която NextLevel чете поръчките |
| `/robots.txt`, `/sitemap*.xml`, `/llms.txt`, `/agents.md` | нямат смисъл да се крият и се ползват от ботовете |

## Как се сменя списъкът

`group_vars/all.yml` → `blocked_countries: ["US", "CA"]`, после:

```bash
ansible-playbook playbooks/deploy_nginx.yml --tags config
```

Празен списък (`blocked_countries: []`) = никой не е блокиран. Само `deploy_nginx.yml` е нужен —
бекендът и фронтендът не се пипат.

## Проверка

```bash
# от сървъра (симулира заглавката на Cloudflare)
curl -sI https://purepeptide.bg/ -H "CF-IPCountry: US" | head -1     # → 403
curl -s  https://purepeptide.bg/ -H "CF-IPCountry: US" | grep -o "not configured"
curl -sI https://purepeptide.bg/ -H "CF-IPCountry: BG" | head -1     # → 200
curl -sI https://purepeptide.bg/ -H "CF-IPCountry: US" \
     -H "User-Agent: Googlebot/2.1" | head -1                        # → 200
```

Автоматично: `pytest backend/tests/test_geoblock_us_ca.py` вдига истински nginx с този шаблон и
проверява всички случаи (19 теста).

## Какво да знаеш

- **Ти самият** няма да отваряш сайта (нито админ панела) през американски или канадски VPN.
- Работи само докато трафикът минава през Cloudflare (оттам идва `CF-IPCountry`). При директна
  заявка към сървъра заглавката липсва и никой не се блокира — Cloudflare Origin сертификатите вече
  затварят този път.
- **Не включвай „Cache Everything“** в Cloudflare за HTML: кеширана страница може да се отдаде на
  американски посетител и блокът да протече. Страницата с грешката се отдава с `no-store`.
- Страницата е `noindex` и не съдържа нито името на магазина, нито думата „blocked“.

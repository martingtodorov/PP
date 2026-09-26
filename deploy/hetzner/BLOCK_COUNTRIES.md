# Блокиране на държави (включено за US и CN)

**25.09.2026: блокирани са САЩ (`US`) и Китай (`CN`).** Посетител от тези държави вижда страницата
„този домейн не е конфигуриран" (`_not-live.html`), а не магазина. Ботовете НЕ се блокират —
Googlebot изрично.

## Как работи

Cloudflare подава държавата в заглавката `CF-IPCountry`, а nginx решава на входа:

```
map $http_cf_ipcountry $pp_geo_blocked { default 0; US 1; CN 1; }               # от blocked_countries
map $http_user_agent   $pp_crawler     { … googlebot|bingbot|gptbot … }
map "$pp_geo_blocked:$pp_crawler" $pp_block { default 0; "1:0" 1; }
```

`if ($pp_block) { return 403; }` стои в локациите, които отдават съдържание (`/`, `= /`, `/api/`,
`/api/files/`), а `error_page 403 /_not-live.html` подменя тялото с нашата страница
(`deploy/hetzner/ansible/files/error-pages/_not-live.html`, инсталира се в
`{{ web_root }}/error-pages/` от `deploy_nginx.yml`).

Защо `if`-ът е в локациите, а не в `server` блока: при `return 403` направо в `server`, nginx
отговаря със собствената си 403 страница и **игнорира** `error_page`.

### Кой НЕ се блокира (индексирането остава непокътнато)

| Изключение | Причина |
| :--------- | :------ |
| Googlebot, Google-InspectionTool, StoreBot-Google, Bingbot, Applebot, Yandex, Baidu, DuckDuckBot, PetalBot, Ahrefs, Semrush | обхождат от американски IP-та — без това изключение спира индексирането в Google и Search Console спира да чете sitemap-ите |
| GPTBot, OAI-SearchBot, ChatGPT-User, PerplexityBot, ClaudeBot, Anthropic, Amazonbot, Meta, Bytespider | AI краулърите също идват от US |
| Facebook, Twitter/X, LinkedIn, WhatsApp, Telegram, Slack, Discord, Pinterest | иначе линковете в социалните мрежи остават без превю |
| UptimeRobot, Pingdom, BetterUptime, StatusCake | мониторингът е от облачни IP-та |
| **Всеки не-браузър User-Agent** (`bot`, `crawler`, `spider`, `curl`, `wget`, `python`, `okhttp`, `java/`, `go-http`, `axios`, `node-fetch`, `postman`, `headless`, `puppeteer`, `playwright`, `lighthouse`, `pagespeed`, `monitor`, `validator`, `feed`, `archive`, Screaming Frog, Sitebulb …) | решение на собственика 25.09.2026: блокират се само **реални посетители** от US/CN. Датацентър трафикът на практика е автоматизация, а ASN проверка на origin-а не е възможна (данните за „verified bots"/ASN в Cloudflare са платена функция), затова всичко, което не е браузър, минава |
| `/robots.txt`, `/sitemap*.xml`, `/llms.txt`, `/agents.md` | отдават се от отделни локации без `$pp_block` — видими за всички |
| `/wp-json/…` | интеграционната точка, по която NextLevel чете поръчките |

Тоест: **нищо от SEO инфраструктурата не е зад блока.** Дори човек от блокирана държава да поиска
`/robots.txt` или sitemap, получава ги нормално — само страниците на магазина са скрити.

## Как се сменя списъкът

Стойността по подразбиране е в `ansible/tasks/infra_defaults.yml`
(`blocked_countries: ['US', 'CN']`). За друг списък — в `group_vars/all.yml`:

```yaml
blocked_countries: ["US", "CN", "IN"]   # или [] за „никой не е блокиран"
```

после:

```bash
ansible-playbook playbooks/deploy_nginx.yml --tags config
```

Само `deploy_nginx.yml` е нужен — блокът е изцяло в nginx конфигурацията.

## Проверка

```bash
# нормален посетител от България → 200
curl -s -o /dev/null -w "%{http_code}\n" -H "CF-IPCountry: BG" https://purepeptide.bg/

# посетител от САЩ → 403 със страницата „домейнът не е конфигуриран"
curl -s -H "CF-IPCountry: US" https://purepeptide.bg/ | head -5

# Googlebot от САЩ → 200 (индексирането не е засегнато)
curl -s -o /dev/null -w "%{http_code}\n" -H "CF-IPCountry: US" \
  -A "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" https://purepeptide.bg/

# SEO файловете са отворени за всички
curl -s -o /dev/null -w "%{http_code}\n" -H "CF-IPCountry: US" https://purepeptide.bg/robots.txt
```

Заглавката `CF-IPCountry` върши работа само при заявка директно към origin-а; през Cloudflare тя се
презаписва от тяхната мрежа, така че от интернет тестът трябва да минава през VPN в съответната
държава.

# PurePeptide — изисквания и текущо състояние

> Актуализирано: 2026-09-24. Комуникация със собственика: **само на български**.
> Старият PRD (1275 реда история) е запазен без загуба в `PRD_HISTORY.md`.
> Изпълнени задачи: `CHANGELOG.md`; приоритети: `ROADMAP.md`; достъп: `test_credentials.md`.

## Първоначална задача
Replacement of a Shopify storefront (PurePeptide) and admin backend using React, FastAPI,
and MongoDB. Port Shopify Liquid templates, theme structures, and Matrixify exports to the
custom stack. Multi-language UI, precise NextLevel/Econt/BoxNow logistics, dynamic checkout,
and Shopify-level technical SEO: server-rendered HTML, structured data and canonicals.

## Потребители и основни изисквания
- Купувач: многоезичен каталог, колекции, продуктови страници, статии, гост чекаут,
  точен офис/автомат/адрес, проследяване и известия.
- Собственик: редакция и преводи, поръчки/клиенти/наличности, анализи, импорт,
  ротация на адреси, отделни 301 препратки, настройки на езици и логистика.
- React + FastAPI + MongoDB; публични API адреси под `/api`.
- URL на preview се чете от `frontend/.env: REACT_APP_BACKEND_URL`.
- MongoDB: `backend/.env: MONGO_URL` и `DB_NAME`; запазват се конфигурациите.
- Домейни: BG root; EU /en /fr /de /cz /hu /pl /sk /si; GR/RO root.
  11 езика + x-default = 12 hreflang връзки.

## Неприкосновени решения
- Публикуваните URL-и, XML sitemap, canonical, hreflang, robots и редиректите не се
  променят произволно. Собственикът потвърди, че са наред в продукция.
- Ротацията остава по език; старият ротиран URL връща 404, не автоматично 301.
- Временна API грешка/timeout/5xx НЕ е основание за noindex.
- **Продуктовото име е винаги единствен H1** и в React, и в пререндера.
  H1 в описанието се преобразува в H2.
- **Не поправяй overflow на менюто**: собственикът изрично отказа на 2026-09-24.
  Пробните промени в `Layout.jsx`/`index.css` са премахнати; файловете съвпадат с началните.
- Не променяй наличности, преводи, съдържание, ротации и подредба при рестарт/обновяване.

## Архитектура и засегнати файлове
- `backend/server.py`: API, MongoDB, ротации; `product_collections()` разрешава историческа
  принадлежност към текущ публикуван локализиран handle, без delisted колекции.
- `backend/i18n.py`: `published_handle()` е източникът за текущия handle.
- `backend/prerender.py`: SSR head/body, кеш; началото и /collections използват
  published_handle; продуктите споделят resolver с API; HTML sitemap използва `/api/link-index`.
- `page_meta`, `articles_index_meta`, `sitemap_meta` в prerender дават общите метаданни
  на SSR и API (`page.seo`, `/articles.seo`, `/link-index.seo`). Запазени са SSR текстовете;
  клиентът вече не реже статичното описание на 155 символа.
- `rotate_page`/`rotate_content` инвалидира кеша непосредствено; generation guard не
  допуска започнал преди ротацията рендер да върне стар резултат в кеша.
- `frontend/src/pages/ProductPage.jsx`, `HtmlSitemapPage.jsx`, `StaticPage.jsx`: съответните
  клиентски поправки. Няма промени по общия SEO hook, дизайна или менюто.
- `backend/scripts/check_internal_links.py`: read-only обход на sitemap страниците и
  вътрешните anchors по всички домейни/езици; директен 200, canonical, източник на счупения линк.
  Не бърка image:loc с URL на HTML страница; не следва редиректи.
  Извиква се и от съществуващия `scripts/check_sitemap.py`.
- `backend/tests/test_iteration54_ssr_links_and_metadata.py`: изолирана временна Mongo база,
  ротации, кеш, всички езици, дълги описания, ASGI crawl и отрицателни контроли.

## Проверено на 2026-09-24
- **35 pytest успешни, 1 пропуснат** (стар тест изисква реална колекция с различен RO handle;
  същият сценарий е покрит с изолирани тестови данни).
- Браузър: точно един продуктов H1, включително при суров H1 в описанието;
  съвпадат title/description на 6 HTML sitemap маршрута, /pages/articles и privacy-policy;
  12 hreflang, parseable JSON-LD, без неочакван noindex. `yarn build` успешен със стари warnings.
- Обход на **демо базата**: 547 адреса, 0 неканонични, 0 счупени цели на HTML anchors.
  Общо 33 sitemap 404: about-1/cookies/scientific-literature липсват за 11 езика.
  Това не е отчет за реалните 679 продукционни URL-а; не са премахвани sitemap entries
  и не е създавано измислено съдържание, за да мине проверката.
- Preview ingress заменя X-Forwarded-Host. За пълен домейн-aware локален обход:
  `python backend/scripts/check_internal_links.py --base "$REACT_APP_BACKEND_URL" --in-process --report audit.json`.
  In-process използва истинските FastAPI маршрути и базата без startup или запис на съдържание.
- Отчети: `test_reports/iteration_54.json`, `iteration_54_final.json`,
  `test_reports/pytest/iter54_final.xml`, `test_reports/internal-links-final.json`.

## Ограничения и следващи задачи
- Preview е с демо каталог (16 продукта/5 статии), не продукционният каталог от доклада.
- NextLevel, Resend, Anthropic и VAPID ключовете са умишлено премахнати: `SECRETS.md`.
  Външните интеграции не са валидирани тук. SEO реализацията НЕ използва мокнати API.
  Само тестовете подменят AI rewrite/описание, за да не викат платени услуги.
- Следващо: същият read-only обход върху пълните продукционни данни.
- P1: ограничаване на честотата на каталожната синхронизация.
- P2: истински продуктови ревюта, покана след доставка, Apple/iOS autofill обратна връзка.

## Финална проверка за деплой — 2026-09-24
- По изричното „Готови ли сме за деплой?“ беше изпълнена проверка за готовност.
- Премахнати са старите destructive startup пътища: seed_catalog вече инициализира само
  напълно празен каталог и не изтрива/презаписва данни, независимо от SEED_VERSION или
  ALLOW_RESEED. Пази и частичен каталог (само колекции/статии, без продукти).
- seed_pages вече не изтрива legacy alias записи при старт. Публичните legacy адреси остават
  404 чрез съществуващите правила; sitemap-ите и текущите URL-и не са променени.
- `tests/test_iteration55_seed_safety.py`: 10 теста с отделна временна Mongo база за тези защити.
- Финален целеви набор: **48 успешни, 1 пропуснат**, `test_reports/pytest/deploy_final.xml`.
  По-широки стари тестове очакват несъществуващи в demo SEO полета/catalog link_key;
  такива data-dependent проверки не бива да се представят за минали.
- Финален deployment health result: **WARN, без BLOCKER**; compilation/env/CORS/services
  проверки са OK; destructive_db_startup_confirmed=false. Предупрежденията са за широки
  startup Mongo cursor обходи в fix_bg_typos/retarget_internal_links/retarget_rotated_links.
  Не са добавяни произволни limit-и, които биха пропуснали линкове/документи.
- `.env` остава извън Git. Ansible подава продукционната конфигурация отделно от хранилището.
- **Не е извършен деплой.** Готовността е за кода; реалните production secrets/data и
  пълният live crawl остават проверки за средата на съществуващия сайт.
# PurePeptide — CHANGELOG
(PRD.md holds the problem statement, architecture and the older history.)

## 2026-06-03 — Локализация на дългите текстове, държава по домейн, ротация на страници
- **„лв.“ по чуждите домейни**: проверено живо на purepeptide.gr / .ro — няма BGN. Поправката
  (`showsBGN() === locale "bg"`) вече е в деплойнатия билд (commit 6db8b12), не се налага нова промяна.
- **Дълги текстове на 10 езика** (`backend/tools/translate_static_blocks.py` → Claude, ключът на
  собственика → `frontend/src/i18n/blocksGenerated.js`): продуктовите блокове (5), картите за доверие (3)
  и FAQ (4) за en/fr/de/cz/hu/pl/sk/si/gr/ro. `locales.js` вече спредва `...PRODUCT_BLOCKS_GEN`,
  `...TRUST_CARDS_GEN`, `...FAQ_GEN`. Блокът „Доставка“ и FAQ-въпросът за доставката са неутрални
  (без „Спиди“ / „наложен платеж“), защото куриерът е различен по държави — сменено и в bg.
- **Държава за доставка по домейн/език** (решение на собственика: домейнът бие IP-то):
  `LOCALE_COUNTRY` / `countryForLocale()` в `i18n/locales.js`; `PreCheckoutModal` стартира с държавата на
  езика (.gr→GR, .ro→RO, /cz→CZ, /si→SI, /pl, /hu, /sk, /de) и **не** позволява на IP-то да я
  презапише; `checkoutPrefetch.prefetchCheckout` подгрява същата държава. Запомненият избор (90 дни)
  остава с най-висок приоритет. Проверено: /gr → Ελλάδα + Speedex + префикс +30.
- **Ротация на статични страници**: `/pages/faq` → `/pages/faq-xyz`. `ROTATABLE` вече включва `pages`;
  `rotate_page()` пази `slug` (админ редакторът не се пипа) и публикува новия адрес в `pub_slug`,
  записва `rotations`. Втора ротация **сменя** трибуквения код, не добавя нов суфикс (същото важи и за
  продукти/колекции/статии — базата е първият `from`). Старият адрес дава 404 само за този език;
  `/api/links`, `/api/link-index` и `sitemap.xml` връщат новия адрес per locale;
  `StaticPage.jsx` ползва `baseSlug = remote.slug` → FAQ акордеонът, контактната форма и калкулаторът
  продължават да работят след ротация.
- **FAQ страница на чужд език**: ако `/api/pages/faq` върне ред с `source_locale !== locale` (превод
  липсва в базата), фронтендът вече ползва локализирания bundle (`FAQ_GEN`) и `t("faq")` за
  заглавието, а английското HTML тяло се скрива.
- Breadcrumb „Начало“ в `StaticPage` вече минава през `t("home")`.
- Тестове: `backend/tests/test_page_rotation.py` (нов, зелен), тестовият агент — iteration_41
  (backend 7/7, frontend 100% след поправката на FAQ страницата).

## 2026-06-03 (втора част) — .eu по IP, селектор за език, NextLevel receiver.country, деплой поправки
- **purepeptide.eu apex** вече не праща всички на `/en`: `LocaleContext` проверява запомнения избор
  (`pp_lang_v1`), после `/api/geo/country` и праща посетителя на неговия език — ако езикът има свой
  домейн (bg/gr/ro) го изпраща там (`window.location.replace`), иначе на префикса (`/de`, `/cz` …).
  Непозната държава → английски. Картата държава→език е в `frontend/src/i18n/geoLocale.js`
  (`COUNTRY_LOCALE`, вкл. CY→gr, MD→ro, AT/CH/LI→de, BE/LU/MC→fr).
- **Селектор за език** (`components/LocaleSwitcher.jsx`): бутон с глобус + код на езика и дропдаун с
  11-те езика, в мобилния хедър до количката и в десктоп хедъра до търсачката, на **всички** домейни.
  Изборът се запомня (и от линковете във футъра) и бие IP-то. Сменя езика **на текущата страница**.
- **NextLevel 400 „The receiver.country field is required“** (поръчка WLH05, econt_office):
  `fulfillment.build_order` слагаше `country` само при доставка до адрес. Сега `receiver.country` се
  изпраща винаги (fallback към `wc_country` от конфигурацията), при офис/автомат се добавя и `place`,
  а при липса на държава грешката е ясна на български, вместо 400 от NextLevel.
  Тестове: `tests/test_fulfillment.py` (+2 нови), 27/27 зелени.
- **Деплой**: `preflight.yml` вече не убива деплоя, когато pp-back излиза в интернет не през pp-front —
  фатално е само липсата на интернет; сравнява се с реалния IP на pp-front и се дава WARNING.
  `inventory.ini.example`: ключът се задава на едно място (`pp_ssh_key`), ProxyCommand носи ключа и за
  jump хоста, `StrictHostKeyChecking=no` + `UserKnownHostsFile=/dev/null` за тунелния 10.0.0.3
  (пресъздаден сървър вече не блокира с „REMOTE HOST IDENTIFICATION HAS CHANGED“).
- Тествано: iteration_42 (backend 27/27, frontend 100% — десктоп + мобилен селектор, запазване на
  страницата при смяна на език, футър линкове, количка/чекаут регресия).

### Отворено- Чиповете с категории под страниците са на български в preview, защото preview базата няма преводи на
  колекциите — в продукция са преведени (проверено: `Απώλεια Βάρους`, …). Няма код за поправяне.
- Ротацията не проверява дали продуктът е скрит / дали има съдържание / дали URL-ът е жив (собственикът
  реши да остане така за момента).
- Cloudflare Origin сертификати за .ro/.eu/.gr, Resend домейн верификация, NextLevel WooCommerce sync —
  чакат действие от собственика.

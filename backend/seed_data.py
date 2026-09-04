"""Seed data for PurePeptide store — mirrors the live purepeptide.bg Shopify catalog.

Handles, prices and images are copied 1:1 from the live store so that existing
URLs, SEO and visuals stay identical after migration.
"""

SEED_VERSION = "2026-06-shopify-mirror-4"

CDN = "https://purepeptide.bg/cdn/shop"
SCDN = "https://cdn.shopify.com/s/files/1/0941/8965/0294/files"

LOCALES = ["bg", "en", "fr", "de", "cz", "hu", "pl", "sk", "si", "gr", "ro"]

COLLECTIONS = [
    {
        "handle": "all-peptides",
        "menu_title": "Всички пептиди",
        "menu_order": 0,
        "title": "Всички пептиди",
        "description": "Пълен каталог на лиофилизирани пептиди с лабораторно доказана чистота над 99%, тествани от Janoshik Labs.",
        "image": f"{CDN}/collections/metabolizm-2324758_82413761-dee9-4190-bed7-91a8b9621c38.jpg?v=1779544790&width=1200",
        "sort_order": 0,
        "translations": {"en": {"title": "All peptides", "handle": "all-peptides"}},
    },
    {
        "handle": "metabolic-studies",
        "menu_title": "Пептиди за Отслабване",
        "menu_order": 1,
        "title": "Отслабване",
        "description": "Пептиди, изследвани във връзка с метаболизъм, апетит и телесен състав.",
        "image": f"{CDN}/collections/metabolizm-2324758_82413761-dee9-4190-bed7-91a8b9621c38.jpg?v=1779544790&width=1200",
        "sort_order": 1,
        "translations": {"en": {"title": "Weight management", "handle": "metabolic-studies"}},
    },
    {
        "handle": "studies-on-healing",
        "menu_title": "Пептиди за Възстановяване",
        "menu_order": 4,
        "title": "Възстановяване",
        "description": "Пептиди, изследвани във връзка с тъканно възстановяване и регенерация.",
        "image": f"{CDN}/collections/vzstanovyavane-9259621_670cb6c8-3a75-4ad5-b7ee-136495c2c962.jpg?v=1779544788&width=1200",
        "sort_order": 2,
        "translations": {"en": {"title": "Recovery", "handle": "studies-on-healing"}},
    },
    {
        "handle": "secretagogues",
        "menu_title": "Пептиди за Мускули",
        "menu_order": 2,
        "title": "Мускули",
        "description": "Секретагоги и пептиди, изследвани във връзка с растежен хормон и мускулна тъкан.",
        "image": f"{CDN}/collections/muskuli-2808574_4489135c-e3a0-47b2-8652-9199810de105.jpg?v=1779544795&width=1200",
        "sort_order": 3,
        "translations": {"en": {"title": "Muscle", "handle": "secretagogues"}},
    },
    {
        "handle": "longevity-and-more",
        "menu_title": "Пептиди за Кожа",
        "menu_order": 6,
        "title": "Кожа",
        "description": "Пептиди, изследвани във връзка с кожа, колаген и процеси на стареене.",
        "image": f"{CDN}/collections/kozha-1728219_12158811-8a29-426f-9051-594de60622d5.png?v=1779544788&width=1200",
        "sort_order": 4,
        "translations": {"en": {"title": "Skin & longevity", "handle": "longevity-and-more"}},
    },
    {
        "handle": "melanin-i-libido",
        "menu_title": "Пептиди за Либидо и Меланин",
        "menu_order": 3,
        "title": "Меланин",
        "description": "Меланокортинови пептиди, изследвани във връзка с пигментация и либидо.",
        "image": f"{CDN}/collections/melanin-2420930_72090954-ce44-49d8-b3a6-5c15f36c07f3.jpg?v=1779544792&width=1200",
        "sort_order": 5,
        "translations": {"en": {"title": "Melanin & libido", "handle": "melanin-i-libido"}},
    },
    {
        "handle": "immunology",
        "menu_title": "Пептиди за Имунитет",
        "menu_order": 5,
        "title": "Имунитет",
        "description": "Пептиди, изследвани във връзка с имунния отговор.",
        "image": f"{CDN}/collections/imunitet-3783452_e038d6b3-fb4c-4e28-b175-b037ba5c7fb8.jpg?v=1779544790&width=1200",
        "sort_order": 6,
        "translations": {"en": {"title": "Immunity", "handle": "immunology"}},
    },
]

_DISCLAIMER = (
    "<p><em>Информацията е събрана и систематизирана от публикувани научни материали, които се отнасят "
    "предимно до клетъчни и животински модели. Текстът служи единствено с образователна и информационна цел "
    "и не представлява медицински съвет, диагноза или препоръка за дозиране.</em></p>"
)

PRODUCTS = [
    {
        "handle": "bpc-157-5",
        "title": "BPC-157 5mg/10mg",
        "subtitle": "Body Protection Compound",
        "description": "<h2>Какво представлява BPC-157?</h2><p>BPC-157 е пентадекапептид, съставен от 15 аминокиселини. Той представлява синтетично изследван пептиден фрагмент, свързан с протеиновия комплекс body protection compound (BPC), описан първоначално във връзка с човешкия стомашен сок.</p><p>BPC-157 е предмет основно на предклинични и лабораторни изследвания, в които се разглежда възможната му връзка с процеси на тъканно възстановяване — мускули, сухожилия, връзки и други структури на съединителната тъкан.</p><h3>Наблюдения при BPC-157</h3><ul><li><strong>Заздравяване на травми</strong> – наблюдения при експериментални модели със сухожилия, мускули и костна тъкан.</li><li><strong>Хронични възпалителни процеси</strong> – промени във възпалителния отговор и локалните тъканни реакции.</li><li><strong>Стомашно-чревна защита</strong> – изменения в лигавичната бариера при експериментални модели.</li><li><strong>Циркулация</strong> – ангиогенеза и микроциркулация в увредени тъкани.</li></ul>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/bpc-157br5mg10mg-5909782_b2b5623f-2c10-4be8-a82f-502ea1c3cefb.png?v=1779544797&width=1200",
        "images": [
            f"{CDN}/files/bpc-157br5mg10mg-5909782_b2b5623f-2c10-4be8-a82f-502ea1c3cefb.png?v=1779544797&width=1200",
            f"{CDN}/files/bpc-157br5mg10mg-1385419_4f4138b6-1afa-45fd-81fc-2c565f6d5abc.png?v=1779544799&width=1200",
            f"{CDN}/files/IMG_2085.png?v=1784550444&width=1200",
        ],
        "variants": [
            {"name": "5mg", "price_eur": 29.00, "stock": 50, "sku": "BPC-5"},
            {"name": "10mg", "price_eur": 49.00, "stock": 30, "sku": "BPC-10"},
        ],
        "collections": ["studies-on-healing", "secretagogues"],
        "tags": ["bpc-157", "регенерация"],
        "specs": {"cas": "137525-51-0", "formula": "C62H98N16O22", "mw": "1419.556 g/mol", "purity": ">98% HPLC"},
        "featured": True,
        "translations": {
            "en": {
                "title": "BPC-157 5mg/10mg",
                "handle": "bpc-157-5",
                "description": "<h2>What is BPC-157?</h2><p>BPC-157 is a pentadecapeptide of 15 amino acids, a synthetic research fragment related to the body protection compound (BPC) originally described in human gastric juice.</p><p>BPC-157 has been studied primarily in preclinical and laboratory models exploring tissue repair processes involving muscle, tendon, ligament and other connective tissue structures.</p>",
            }
        },
    },
    {
        "handle": "fgtb-500",
        "title": "TB-500 (frag. 17-23) 10mg",
        "subtitle": "Thymosin beta-4 фрагмент",
        "description": "<h2>Какво представлява TB-500?</h2><p>TB-500 е синтетичен фрагмент (17-23) на тимозин бета-4 — естествено срещащ се пептид, изследван във връзка с клетъчна миграция, ангиогенеза и тъканно възстановяване.</p><p>Публикуваните данни са предимно от лабораторни и животински модели и не установяват клинична ефективност при хора.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/tb-500-frag-17-23br5mg10mg-2753046_00c9e91e-c9ae-4c84-8262-6832dc337d9e.png?v=1779544795&width=1200",
        "variants": [{"name": "10mg", "price_eur": 49.00, "stock": 22, "sku": "TB-10"}],
        "collections": ["studies-on-healing"],
        "tags": ["tb-500"],
        "specs": {"cas": "885340-08-9", "formula": "C38H68N10O14", "mw": "889.01 g/mol", "purity": ">98% HPLC"},
        "featured": True,
    },
    {
        "handle": "2-tesamorelin",
        "title": "Тесаморелин (Tesamorelin) 10mg",
        "subtitle": "GHRH аналог",
        "description": "<h2>Какво представлява Tesamorelin?</h2><p>Тесаморелин е стабилизиран аналог на растежен хормон-освобождаващия хормон (GHRH), изследван във връзка с ендогенната секреция на GH и метаболизма на висцералната мастна тъкан.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/Tesamorelin_8c44169b-0e78-4605-ba6e-62b1f340ea5c.png?v=1779544834&width=1200",
        "variants": [{"name": "10mg", "price_eur": 59.00, "stock": 20, "sku": "TESA-10"}],
        "collections": ["metabolic-studies", "secretagogues"],
        "tags": ["ghrh"],
        "specs": {"cas": "901758-09-6", "formula": "C223H370N72O69S", "mw": "5195.908 g/mol", "purity": ">98% HPLC"},
        "featured": True,
    },
    {
        "handle": "mots-c",
        "title": "MOTS-c 10mg",
        "subtitle": "Митохондриален пептид",
        "description": "<h2>Какво представлява MOTS-c?</h2><p>MOTS-c е митохондриално кодиран пептид от 16 аминокиселини, изследван във връзка с метаболитна регулация, инсулинова чувствителност и AMPK сигнализация.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/MOTS-c_4aea18a0-0bd0-4fb9-b3d4-a92d85a6d26b.png?v=1779544795&width=1200",
        "variants": [{"name": "10mg", "price_eur": 45.00, "stock": 24, "sku": "MOTS-10"}],
        "collections": ["metabolic-studies", "studies-on-healing"],
        "tags": ["mots-c"],
        "specs": {"cas": "1627580-64-6", "formula": "C101H152N28O22S2", "mw": "2174.64 g/mol", "purity": ">98% HPLC"},
        "featured": True,
    },
    {
        "handle": "1-ghk-cu",
        "title": "GHK-Cu (меден пептид) 100mg",
        "subtitle": "Меден трипептид",
        "description": "<h2>Какво представлява GHK-Cu?</h2><p>GHK-Cu е меден трипептид (глицил-L-хистидил-L-лизин), изследван във връзка с генна експресия, синтез на колаген и защита срещу оксидативен стрес в кожни модели.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/ghk-cu-skin-glowbr100mg-4384070_9a5d0ca6-b42a-4dfe-bdd8-f9602f9660d9.png?v=1779544804&width=1200",
        "variants": [{"name": "100mg", "price_eur": 39.00, "stock": 18, "sku": "GHK-100"}],
        "collections": ["longevity-and-more"],
        "tags": ["ghk-cu", "кожа"],
        "specs": {"cas": "89030-95-5", "formula": "C14H22CuN6O4", "mw": "401.91 g/mol", "purity": ">98% HPLC"},
        "featured": True,
    },
    {
        "handle": "pp-thymosin-beta-4",
        "title": "Тимозин бета-4 (Thymosin beta-4) 5mg",
        "subtitle": "Регенеративен пептид",
        "description": "<h2>Какво представлява Thymosin beta-4?</h2><p>Тимозин бета-4 е пептид от 43 аминокиселини, изследван във връзка с актиновата динамика, клетъчната миграция и тъканното възстановяване.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/timozin-beta-4brthymosin-beta-4-5mg-9632338_2d3f8e1a-c921-4ca6-8088-83ed4ff29bce.png?v=1779544796&width=1200",
        "variants": [{"name": "5mg", "price_eur": 49.00, "stock": 20, "sku": "TB4-5"}],
        "collections": ["studies-on-healing", "immunology"],
        "tags": ["тимозин"],
        "specs": {"cas": "77591-33-4", "formula": "C212H350N56O78S", "mw": "4963.44 g/mol", "purity": ">98% HPLC"},
        "featured": True,
    },
    {
        "handle": "3-ipamorelin-1",
        "title": "Ипаморелин (Ipamorelin) 10mg",
        "subtitle": "Селективен GH секретагог",
        "description": "<h2>Какво представлява Ipamorelin?</h2><p>Ипаморелин е селективен пентапептиден агонист на грелиновия рецептор, изследван във връзка с освобождаването на растежен хормон при минимално повлияване на кортизол и пролактин в експериментални модели.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/ipamorelin-ipamorelinbr10mg-9325709_a80fd981-aa41-4801-b17c-16cd74bfd1d2.png?v=1779544802&width=1200",
        "variants": [{"name": "10mg", "price_eur": 49.00, "stock": 16, "sku": "IPA-10"}],
        "collections": ["secretagogues"],
        "tags": ["gh"],
        "specs": {"cas": "170851-70-4", "formula": "C38H49N9O5", "mw": "711.86 g/mol", "purity": ">98% HPLC"},
        "featured": True,
    },
    {
        "handle": "acjc-1295",
        "title": "CJC-1295 (no DAC) 5mg",
        "subtitle": "GHRH аналог",
        "description": "<h2>Какво представлява CJC-1295?</h2><p>CJC-1295 без DAC (модифициран GRF 1-29) е аналог на GHRH, изследван във връзка с пулсативната секреция на растежен хормон и оста GH/IGF-1.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/cjc-1295-no-dacbr5mg-2052321_1247463f-acf2-41a5-80a6-f6dff48584af.png?v=1779544802&width=1200",
        "variants": [{"name": "5mg", "price_eur": 45.00, "stock": 26, "sku": "CJC-5"}],
        "collections": ["secretagogues"],
        "tags": ["ghrh"],
        "specs": {"cas": "863288-34-0", "formula": "C152H252N44O42", "mw": "3367.9 g/mol", "purity": ">98% HPLC"},
        "featured": True,
    },
    {
        "handle": "axchgh-frag-176-191",
        "title": "hGH frag (176-191) 5mg",
        "subtitle": "Фрагмент на растежен хормон",
        "description": "<h2>Какво представлява hGH frag 176-191?</h2><p>Фрагмент 176-191 на човешкия растежен хормон е изследван във връзка с липолизата в мастна тъкан в експериментални модели, без описаните ефекти върху растежа, характерни за целия хормон.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/hgh-frag-176-191br5mg-3748012_c7410536-5990-4c10-9435-3a63dfd65ce5.png?v=1779544815&width=1200",
        "variants": [{"name": "5mg", "price_eur": 35.00, "stock": 28, "sku": "HGH-5"}],
        "collections": ["metabolic-studies"],
        "tags": ["fat-loss"],
        "specs": {"cas": "66004-57-7", "formula": "C78H125N23O23S2", "mw": "1817.12 g/mol", "purity": ">98% HPLC"},
    },
    {
        "handle": "pt-141",
        "title": "PT-141 10mg",
        "subtitle": "Bremelanotide",
        "description": "<h2>Какво представлява PT-141?</h2><p>PT-141 (бремеланотид) е меланокортинов рецепторен агонист, изследван във връзка с централни механизми на сексуална възбуда.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/pt-141-bremelanotidebr10mg-1779039_15608a5c-ae64-4a4b-ab7b-74fb471475a2.png?v=1779544818&width=1200",
        "variants": [{"name": "10mg", "price_eur": 49.00, "stock": 14, "sku": "PT-10"}],
        "collections": ["melanin-i-libido"],
        "tags": ["либидо"],
        "specs": {"cas": "189691-06-3", "formula": "C50H68N14O10", "mw": "1025.2 g/mol", "purity": ">98% HPLC"},
    },
    {
        "handle": "dsip-5mg",
        "title": "DSIP (Delta Sleep Inducing Peptide) 5mg",
        "subtitle": "Делта сън-индуциращ пептид",
        "description": "<h2>Какво представлява DSIP?</h2><p>DSIP е нонапептид, изследван във връзка с делта фазите на съня, невроендокринната регулация и стресовия отговор.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/dsip-delta-sleep-inducing-peptidebr5mg-7647068_f66d56ef-1657-4520-9b5c-94c3c08e887f.png?v=1779544809&width=1200",
        "variants": [{"name": "5mg", "price_eur": 39.00, "stock": 21, "sku": "DSIP-5"}],
        "collections": ["studies-on-healing"],
        "tags": ["сън"],
        "specs": {"cas": "62568-57-4", "formula": "C35H48N10O15", "mw": "848.8 g/mol", "purity": ">98% HPLC"},
    },
    {
        "handle": "melanotan-ii",
        "title": "Меланотан I (Melanotan I) 10mg",
        "subtitle": "Меланокортинов аналог",
        "description": "<h2>Какво представлява Melanotan I?</h2><p>Меланотан I (афамеланотид) е синтетичен аналог на α-MSH, изследван във връзка с меланогенезата и фотопротекцията в експериментални модели.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/melanotan-melanotan-ibr10mg-5045985_126df4ad-dfbe-4a5d-bbfd-ebb109b1f6e7.png?v=1779544817&width=1200",
        "variants": [{"name": "10mg", "price_eur": 49.00, "stock": 19, "sku": "MT1-10"}],
        "collections": ["melanin-i-libido"],
        "tags": ["меланин"],
        "specs": {"cas": "75921-69-6", "formula": "C78H111N21O19", "mw": "1646.86 g/mol", "purity": ">98% HPLC"},
    },
    {
        "handle": "thymosin-alpha-1",
        "title": "Тимозин алфа-1 (Thymosin alpha-1) 5mg",
        "subtitle": "Имуномодулатор",
        "description": "<h2>Какво представлява Thymosin alpha-1?</h2><p>Тимозин алфа-1 е пептид от 28 аминокиселини, изследван във връзка с модулация на Т-клетъчния отговор и вродения имунитет.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/timozin-alfa-1-thymosin-alpha-1br5mg-2531193_6bc18ff6-b9a4-4030-bb04-9c8e4cbfe924.png?v=1779544820&width=1200",
        "variants": [{"name": "5mg", "price_eur": 59.00, "stock": 12, "sku": "TA1-5"}],
        "collections": ["immunology"],
        "tags": ["имунитет"],
        "specs": {"cas": "62304-98-7", "formula": "C129H215N33O55", "mw": "3108.3 g/mol", "purity": ">98% HPLC"},
    },
    {
        "handle": "aaigf-lr3",
        "title": "IGF-1 LR3 (Long arginine 3) 1mg",
        "subtitle": "Инсулиноподобен растежен фактор",
        "description": "<h2>Какво представлява IGF-1 LR3?</h2><p>IGF-1 LR3 е дългодействащ аналог на инсулиноподобния растежен фактор 1, изследван във връзка с клетъчна пролиферация и анаболни сигнални пътища.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/1-2_2f7ea207-3d0e-4104-8739-63a173bc50bc.png?v=1779544789&width=1200",
        "variants": [{"name": "1mg", "price_eur": 69.00, "stock": 10, "sku": "IGF-1"}],
        "collections": ["secretagogues"],
        "tags": ["igf"],
        "specs": {"cas": "946870-92-4", "formula": "C400H625N111O116S9", "mw": "9117.5 g/mol", "purity": ">98% HPLC"},
    },
    {
        "handle": "vdgfghrp-6",
        "title": "GHRP-6 5mg",
        "subtitle": "Растежен хормон-освобождаващ пептид",
        "description": "<h2>Какво представлява GHRP-6?</h2><p>GHRP-6 е хексапептид, изследван във връзка с грелиновия рецептор, освобождаването на растежен хормон и апетита в експериментални модели.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/ghrp-6br5mg-6213283_249ea8e0-0b30-4eb6-b2f1-2e693cb95c5c.png?v=1779544809&width=1200",
        "variants": [{"name": "5mg", "price_eur": 29.00, "stock": 30, "sku": "GHRP6-5"}],
        "collections": ["secretagogues"],
        "tags": ["ghrp"],
        "specs": {"cas": "87616-84-0", "formula": "C46H56N12O6", "mw": "873.01 g/mol", "purity": ">98% HPLC"},
    },
    {
        "handle": "sermorelin",
        "title": "Серморелин (Sermorelin) 5mg",
        "subtitle": "GHRH (1-29)",
        "description": "<h2>Какво представлява Sermorelin?</h2><p>Серморелин е аналог на GHRH (1-29), изследван във връзка със стимулирането на естествената секреция на растежен хормон.</p>"
        + _DISCLAIMER,
        "image": f"{CDN}/files/sermorelin-sermorelinbr5mg10mg-2113533_2eb21a45-0060-4364-af55-c9df858579de.png?v=1779544801&width=1200",
        "variants": [{"name": "5mg", "price_eur": 59.00, "stock": 14, "sku": "SER-5"}],
        "collections": ["secretagogues", "longevity-and-more"],
        "tags": ["ghrh"],
        "specs": {"cas": "86168-78-7", "formula": "C149H246N44O42S", "mw": "3357.9 g/mol", "purity": ">98% HPLC"},
    },
]

ARTICLES = [
    {
        "handle": "tesamorelin",
        "title": "Tesamorelin: фармакология, метаболитни ефекти и изследователско значение",
        "excerpt": "Преглед на механизма на действие на тесаморелин, връзката му с оста GH/IGF-1 и метаболитните наблюдения в публикуваните изследвания.",
        "image": f"{CDN}/articles/Tesamorelin_54de73be-2b5a-4103-a990-14cba2455c3b.png?v=1780239534&width=1200",
        "product_handle": "2-tesamorelin",
    },
    {
        "handle": "mots-c",
        "title": "MOTS-c пептид: митохондриален сигнален фактор и метаболитни ефекти",
        "excerpt": "Как митохондриално кодираният пептид MOTS-c повлиява AMPK сигнализацията и метаболитния профил в експериментални модели.",
        "image": f"{CDN}/articles/Mots-c_b50faab9-9c1c-4709-8195-c3f3f4b57337.png?v=1780239550&width=1200",
        "product_handle": "mots-c",
    },
    {
        "handle": "triumph3-study-on-retatrutide",
        "title": "Retatrutide – троен GIP, GLP-1 и глюкагонов агонист при затлъстяване",
        "excerpt": "Данни от изследванията върху ретатрутид и потенциалът на тройната рецепторна агонистична активност.",
        "image": f"{CDN}/articles/RETA_99257008-1e20-4252-a424-1ff1acecbf79.jpg?v=1787313445&width=1200",
        "product_handle": "",
    },
    {
        "handle": "ghk-cu-gene-data",
        "title": "Регенеративни и защитни действия на GHK-Cu в светлината на новите генни данни",
        "excerpt": "Медният трипептид GHK-Cu и влиянието му върху генната експресия, колагена и възстановителните процеси в кожата.",
        "image": f"{CDN}/articles/GHK_8e67896e-9779-48bf-bf1c-8494966832d0.png?v=1780239600&width=1200",
        "product_handle": "1-ghk-cu",
    },
    {
        "handle": "cjc-1295-gh-igf1",
        "title": "Активиране на оста GH/IGF-1 чрез CJC-1295 – дългодействащ аналог на GHRH",
        "excerpt": "Механизъм на действие на CJC-1295 и наблюденията върху пулсативната секреция на растежен хормон.",
        "image": f"{CDN}/articles/CJC_2d302ecf-fcca-4497-9257-478a295c1148.png?v=1780239578&width=1200",
        "product_handle": "acjc-1295",
    },
]

BRAND_LOGOS = [
    f"{SCDN}/IMG_2354.webp?v=1767538317",
    f"{SCDN}/IMG_2351.webp?v=1767538317",
    f"{SCDN}/IMG_2357.webp?v=1767538316",
    f"{SCDN}/IMG_2353.webp?v=1767538316",
    f"{SCDN}/IMG_2352.webp?v=1767538316",
    f"{SCDN}/IMG_2356.webp?v=1767538317",
    f"{SCDN}/IMG_2355.webp?v=1767538317",
]

DEFAULT_SETTINGS = {
    "site_name": "PurePeptide",
    "tagline": "Пептиди с лабораторно доказано качество и >99% чистота",
    "hero_title": "PurePeptide",
    "hero_kicker": "Лабораторно анализирани пептиди",
    "hero_subtitle": "Лиофилизирани пептиди за научно-изследователски цели, създадени с фокус върху стабилност, чистота и проследимост. Всеки продукт е придружен от независим анализ от Janoshik Labs.",
    "hero_cta_primary": "Пазарувай пептиди",
    "hero_cta_secondary": "Виж Сертификати",
    "announcements": [
        "✅ Потвърдено качество >99% от лаборатория Janoshik",
        "🚚 Експресна доставка със Спиди за 1-3 работни дни",
        "💵 Наложен платеж при доставка",
    ],
    "announcements_i18n": {
        "en": [
            "✅ Verified purity >99% by Janoshik laboratory",
            "🚚 Express delivery in 1-3 business days",
            "💵 Cash on delivery available",
        ],
        "fr": [
            "✅ Pureté vérifiée >99 % par le laboratoire Janoshik",
            "🚚 Livraison express en 1 à 3 jours ouvrés",
            "💵 Paiement à la livraison disponible",
        ],
        "de": [
            "✅ Geprüfte Reinheit >99 % durch Janoshik Labor",
            "🚚 Expressversand in 1-3 Werktagen",
            "💵 Zahlung per Nachnahme möglich",
        ],
        "cz": [
            "✅ Ověřená čistota >99 % laboratoří Janoshik",
            "🚚 Expresní doručení za 1-3 pracovní dny",
            "💵 Platba na dobírku",
        ],
        "hu": [
            "✅ Igazolt tisztaság >99% a Janoshik laboratóriumtól",
            "🚚 Expressz szállítás 1-3 munkanap alatt",
            "💵 Utánvétes fizetés",
        ],
        "pl": [
            "✅ Potwierdzona czystość >99% przez laboratorium Janoshik",
            "🚚 Dostawa ekspresowa w 1-3 dni robocze",
            "💵 Płatność za pobraniem",
        ],
        "sk": [
            "✅ Overená čistota >99 % laboratóriom Janoshik",
            "🚚 Expresné doručenie za 1-3 pracovné dni",
            "💵 Platba na dobierku",
        ],
        "si": [
            "✅ Preverjena čistost >99 % s strani laboratorija Janoshik",
            "🚚 Hitra dostava v 1-3 delovnih dneh",
            "💵 Plačilo po povzetju",
        ],
        "gr": [
            "✅ Επιβεβαιωμένη καθαρότητα >99% από το εργαστήριο Janoshik",
            "🚚 Ταχεία αποστολή σε 1-3 εργάσιμες ημέρες",
            "💵 Πληρωμή με αντικαταβολή",
        ],
        "ro": [
            "✅ Puritate verificată >99% de laboratorul Janoshik",
            "🚚 Livrare expres în 1-3 zile lucrătoare",
            "💵 Plata la livrare disponibilă",
        ],
    },
    "announcement": "✅ Потвърдено качество >99% от лаборатория Janoshik",
    "brand_logos": BRAND_LOGOS,
    "currency_primary": "EUR",
    "currency_secondary": "BGN",
    "fx_rate": 1.95583,
    "footer_text": "Информацията на този уебсайт е обобщена от множество научни изследвания и анализи. Тя има изцяло информативен характер. Продуктите са предназначени за лабораторни и научноизследователски цели.",
    "contact_email": "info@purepeptide.bg",
    "contact_phone": "+359 88 123 4567",
    "seed_version": SEED_VERSION,
    "resend_api_key": "",
    "resend_from": "PurePeptide <onboarding@resend.dev>",
    # bank transfer instructions — shown on the confirmation page and in the order e-mail
    "bank_name": "DSK Bank",
    "bank_iban": "BG61STSA93000032400775",
    "bank_bic": "STSABGSF",
    "bank_holder": "Purepeptide LTD",
    # seller details printed on invoices / order e-mails
    "company_name": "Purepeptide LTD",
    "company_eik": "",
    "company_vat": "",
    "company_address": "",
    # Editable per-locale routing: which domain / URL prefix / homepage path each language uses.
    "locale_routes": {
        "bg": {"origin": "https://purepeptide.bg", "prefix": "", "home_path": "/", "enabled": True},
        "en": {"origin": "https://purepeptide.eu", "prefix": "/en", "home_path": "/", "enabled": True},
        "fr": {"origin": "https://purepeptide.eu", "prefix": "/fr", "home_path": "/", "enabled": True},
        "de": {"origin": "https://purepeptide.eu", "prefix": "/de", "home_path": "/", "enabled": True},
        "cz": {"origin": "https://purepeptide.eu", "prefix": "/cz", "home_path": "/", "enabled": True},
        "hu": {"origin": "https://purepeptide.eu", "prefix": "/hu", "home_path": "/", "enabled": True},
        "pl": {"origin": "https://purepeptide.eu", "prefix": "/pl", "home_path": "/", "enabled": True},
        "sk": {"origin": "https://purepeptide.eu", "prefix": "/sk", "home_path": "/", "enabled": True},
        "si": {"origin": "https://purepeptide.eu", "prefix": "/si", "home_path": "/", "enabled": True},
        "gr": {"origin": "https://purepeptide.gr", "prefix": "", "home_path": "/", "enabled": True},
        "ro": {"origin": "https://purepeptide.ro", "prefix": "", "home_path": "/", "enabled": True},
    },
    "discount_codes": [
        {"code": "WELCOME10", "type": "percent", "value": 10, "min_subtotal": 0, "active": True},
        {"code": "PEPTIDE20", "type": "percent", "value": 20, "min_subtotal": 100, "active": True},
        {"code": "SHIP5", "type": "fixed", "value": 5, "min_subtotal": 50, "active": True},
    ],
}

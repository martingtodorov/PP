"""Default content for the editable static pages (Bulgarian source + English pivot).

Slugs mirror the live purepeptide.bg URLs 1:1.
"""

PAGE_SLUGS = [
    "какво-са-пептиди",
    "faq",
    "contact-1",
    "chemical-analysis",
    "become-a-distributor",
    "about-1",
    "cookies",
    "scientific-literature",
    "privacy-policy",
    "refund-policy",
    "terms-conditions",
    "delivery-and-payment",
]

PAGE_LABELS = {
    "какво-са-пептиди": "Какво са пептидите",
    "faq": "Често задавани въпроси (FAQ)",
    "contact-1": "Контакти",
    "chemical-analysis": "Химичен анализ",
    "become-a-distributor": "Партньори",
    "about-1": "За нас",
    "cookies": "Бисквитки",
    "scientific-literature": "Научни изследвания",
    "privacy-policy": "Политика за поверителност",
    "refund-policy": "Възстановяване на суми",
    "terms-conditions": "Общи условия",
    "delivery-and-payment": "Доставка и плащане",
}

DEFAULT_PAGES = {
    "какво-са-пептиди": {
        "bg": {
            "title": "Какво са пептидите?",
            "html": "<p>Пептидите са къси вериги от аминокиселини, свързани чрез пептидни връзки. В организма те действат като сигнални молекули и участват в регулацията на метаболизъм, възстановяване на тъкани, имунен отговор и много други процеси.</p><h2>Лиофилизирана форма</h2><p>Всички наши пептиди се доставят в лиофилизирана (изсушена чрез замразяване) форма. Тя запазва структурата и биологичната активност значително по-дълго от готовите водни разтвори.</p><h2>Изследователска употреба</h2><p>Продуктите са предназначени изключително за лабораторни и научноизследователски цели.</p>",
        },
        "en": {
            "title": "What are peptides?",
            "html": "<p>Peptides are short chains of amino acids linked by peptide bonds. In the body they act as signalling molecules involved in metabolism, tissue repair, immune response and many other processes.</p><h2>Lyophilised form</h2><p>All of our peptides ship lyophilised (freeze-dried), which preserves structure and biological activity far longer than pre-mixed aqueous solutions.</p><h2>Research use</h2><p>All products are intended strictly for laboratory and research purposes.</p>",
        },
    },
    "chemical-analysis": {
        "bg": {
            "title": "Химичен анализ и сертификати",
            "html": "<p>Всяка партида преминава HPLC и LC-MS анализ в независимата чешка лаборатория <strong>Janoshik Analytical</strong>. Анализът потвърждава идентичност, чистота (&gt;99%) и съдържание на пептида.</p><h2>Какво съдържа сертификатът</h2><ul><li>Партиден номер и дата на анализ</li><li>HPLC хроматограма с процент чистота</li><li>Масспектрометрично потвърждение на молекулната маса</li><li>Съдържание на нетен пептид</li></ul>",
        },
        "en": {
            "title": "Laboratory analysis & certificates",
            "html": "<p>Every batch undergoes HPLC and LC-MS analysis at the independent Czech laboratory <strong>Janoshik Analytical</strong>, confirming identity, purity (&gt;99%) and net peptide content.</p><h2>What the certificate contains</h2><ul><li>Batch number and analysis date</li><li>HPLC chromatogram with purity percentage</li><li>Mass-spectrometry confirmation of molecular weight</li><li>Net peptide content</li></ul>",
        },
    },
    "contact-1": {
        "bg": {
            "title": "Контакти",
            "html": "<p>Свържете се с нас за въпроси относно продукти, поръчки и доставки.</p><p>Имейл: <a href='mailto:info@purepeptide.bg'>info@purepeptide.bg</a><br>Работно време: понеделник – петък, 9:00 – 18:00</p><p>Доставки се извършват със Спиди в рамките на 1–3 работни дни.</p>",
        },
        "en": {
            "title": "Contact",
            "html": "<p>Get in touch about products, orders and shipping.</p><p>Email: <a href='mailto:info@purepeptide.eu'>info@purepeptide.eu</a><br>Hours: Monday – Friday, 9:00 – 18:00 CET</p>",
        },
    },
    "become-a-distributor": {
        "bg": {
            "title": "Партньори",
            "html": "<p>Работим с независими лаборатории и научни партньори, които подпомагат контрола на качеството и достоверността на публикуваната информация.</p><ul><li>Janoshik Analytical — HPLC / LC-MS анализи</li><li>Специализирани дистрибутори за научни консумативи</li></ul><p>За партньорски запитвания ни пишете на info@purepeptide.bg.</p>",
        },
        "en": {
            "title": "Partners",
            "html": "<p>We work with independent laboratories and research partners supporting quality control and the accuracy of the published information.</p><ul><li>Janoshik Analytical — HPLC / LC-MS testing</li><li>Specialised distributors of research consumables</li></ul>",
        },
    },
    "privacy-policy": {
        "bg": {"title": "Политика за поверителност", "html": "<p>Обработваме лични данни само за изпълнение на поръчки и комуникация, свързана с тях. Не предоставяме данни на трети страни извън необходимите за доставка партньори.</p>"},
        "en": {"title": "Privacy policy", "html": "<p>We process personal data only to fulfil orders and related communication. Data is never shared beyond the partners required for delivery.</p>"},
    },
    "refund-policy": {
        "bg": {"title": "Правила за възстановяване на суми", "html": "<p>Приемаме връщане на неотворени продукти в оригинална опаковка в рамките на 14 дни от получаването. Възстановяването се извършва по същия начин на плащане.</p>"},
        "en": {"title": "Refund policy", "html": "<p>Unopened products in original packaging can be returned within 14 days of delivery. Refunds are issued via the original payment method.</p>"},
    },
    "terms-conditions": {
        "bg": {"title": "Общи условия", "html": "<p>Използвайки този сайт, потвърждавате, че сте на възраст над 18 години и че поръчвате продуктите изключително за лабораторни и научноизследователски цели. Продуктите не са лекарствени средства.</p>"},
        "en": {"title": "Terms of service", "html": "<p>By using this site you confirm that you are over 18 and that you purchase the products strictly for laboratory and research purposes. The products are not medicinal products.</p>"},
    },
    "delivery-and-payment": {
        "bg": {"title": "Доставка и плащане", "html": "<p>Поръчките се обработват в рамките на 1–3 работни дни и се изпращат със Спиди до офис или адрес. Получавате имейл с товарителница след изпращане.</p>"},
        "en": {"title": "Shipping & payment", "html": "<p>Orders are processed within 1–3 business days and shipped with a tracked courier. A tracking email is sent once the parcel leaves our facility.</p>"},
    },
    "faq": {
        "bg": {
            "title": "Често задавани въпроси",
            "html": "",
            "faq_items": [
                {"q": "Какво отличава пептидите на PurePeptide?", "a": "Прозрачност и контрол на качеството. Всеки продукт е лиофилизиран за по-дълъг срок на съхранение и е преминал HPLC и LC-MS анализ с чистота над 99%. Тестовете се извършват от чешката лаборатория Janoshik."},
                {"q": "Как мога да проверя сертификатите за анализ?", "a": "Всеки продукт разполага със сертификат за анализ (CoA), извършен от Janoshik Labs. Документите са достъпни в продуктовите страници и съдържат партиден номер."},
                {"q": "Колко време са стабилни неразтворените пептиди?", "a": "В лиофилизиран вид при 2–8°C пептидите запазват стабилност до 24 месеца. При стайна температура – около 3–4 месеца."},
                {"q": "Колко време отнема доставката?", "a": "Работим със Спиди. Пратките обикновено пристигат в рамките на 1–3 работни дни."},
            ],
        },
        "en": {
            "title": "Frequently asked questions",
            "html": "",
            "faq_items": [
                {"q": "What makes PurePeptide peptides different?", "a": "Transparency and quality control. Every product is lyophilised for a longer shelf life and has passed HPLC and LC-MS analysis with purity above 99%, tested by the Czech Janoshik laboratory."},
                {"q": "How can I check the certificates of analysis?", "a": "Every product has a certificate of analysis (CoA) from Janoshik Labs, available on the product page including the batch number."},
                {"q": "How long are unreconstituted peptides stable?", "a": "Lyophilised at 2–8°C peptides remain stable for up to 24 months; at room temperature roughly 3–4 months."},
                {"q": "How long does shipping take?", "a": "Parcels are shipped with a tracked courier and usually arrive within 1–3 business days."},
            ],
        },
    },
}

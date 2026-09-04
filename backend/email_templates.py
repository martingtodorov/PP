"""Localised, Shopify-style HTML email templates (order confirmation + abandoned cart).

All 11 storefront languages are covered. Rendering is pure string building so the
templates work without any extra dependency.
"""
import os
from typing import Any, Dict, List, Optional

BRAND = "#FE6F61"
DARK = "#0f172a"

LOCALE_ORIGIN = {
    "bg": "https://purepeptide.bg",
    "en": "https://purepeptide.eu/en",
    "fr": "https://purepeptide.eu/fr",
    "de": "https://purepeptide.eu/de",
    "cz": "https://purepeptide.eu/cz",
    "hu": "https://purepeptide.eu/hu",
    "pl": "https://purepeptide.eu/pl",
    "sk": "https://purepeptide.eu/sk",
    "si": "https://purepeptide.eu/si",
    "gr": "https://purepeptide.gr",
    "ro": "https://purepeptide.ro",
}

T: Dict[str, Dict[str, str]] = {
    "bg": {
        "order": "Поръчка", "subject_order": "Поръчка {n} · PurePeptide",
        "title": "Благодарим ви за покупката!", "hello": "Здравейте, {name},",
        "body_ship": "Подготвяме поръчката ви за изпращане. Ще ви известим, когато бъде изпратена.",
        "body_bank": "Ще получите потвърждение по имейл веднага след като плащането постъпи.",
        "summary": "Обобщение на поръчката", "subtotal": "Междинна сума", "discount": "Отстъпка",
        "shipping": "Доставка", "total": "Обща сума", "free": "Безплатно", "saved": "Спестихте",
        "customer_info": "Информация за клиента", "ship_addr": "Адрес за доставка",
        "delivery_method": "Начин на доставка", "payment": "Плащане",
        "cod": "Наложен платеж при получаване", "bank": "Банков превод",
        "bank_details": "Данни за банков превод", "holder": "Получател", "iban": "IBAN",
        "bic": "BIC", "reference": "Основание", "view_order": "Прегледайте поръчката си",
        "or_visit": "или", "visit_shop": "Посетете нашия магазин",
        "footer": "Ако имате въпроси, отговорете на този имейл или ни пишете на",
        "disclaimer": "Продуктите са предназначени единствено за научноизследователски цели.",
        "ab_subject": "Забравихте нещо в количката си 👀", "ab_title": "Вашата количка ви чака",
        "ab_body": "Запазихме артикулите ви. Завършете поръчката си само с няколко клика.",
        "ab_cta": "Завърши поръчката", "qty": "бр.",
        "sh_subject": "Поръчка {n} е на път 🚚", "sh_title": "Пратката ви е на път", "sh_body": "Товарителницата за поръчка {n} е издадена. Можете да следите пратката при куриера или в страницата на поръчката.", "sh_courier": "Куриер",
        "dv_subject": "Поръчка {n} е доставена ✅", "dv_title": "Пратката ви е доставена", "dv_body": "Поръчка {n} е доставена. Благодарим ви, че избрахте PurePeptide! Ако имате въпроси, отговорете на този имейл.",
        "sh_awb": "Номер на товарителница", "sh_track": "Проследи пратката", "sh_view": "Виж поръчката", "sh_cod": "Сума за плащане при получаване",
        "cx_subject": "Поръчка {n} е отказана · PurePeptide", "cx_title": "Поръчката е отказана",
        "cx_body": "Поръчка {n} е отказана и няма да бъде изпратена. Няма какво да плащате. Ако това е по грешка или искате да поръчате отново, просто отговорете на този имейл.", "cx_reason": "Причина",
        "pr_subject": "Плащането по поръчка {n} е получено · PurePeptide", "pr_title": "Плащането е потвърдено", "pr_body": "Получихме плащането по поръчка {n}. Подготвяме я за изпращане и ще ви уведомим, щом тръгне.",
    },
    "en": {
        "order": "Order", "subject_order": "Order {n} · PurePeptide",
        "title": "Thank you for your purchase!", "hello": "Hi {name},",
        "body_ship": "We are preparing your order for shipment. We'll let you know once it ships.",
        "body_bank": "You will receive a confirmation email as soon as your payment arrives.",
        "summary": "Order summary", "subtotal": "Subtotal", "discount": "Discount",
        "shipping": "Shipping", "total": "Total", "free": "Free", "saved": "You saved",
        "customer_info": "Customer information", "ship_addr": "Shipping address",
        "delivery_method": "Shipping method", "payment": "Payment",
        "cod": "Cash on delivery", "bank": "Bank transfer",
        "bank_details": "Bank transfer details", "holder": "Beneficiary", "iban": "IBAN",
        "bic": "BIC", "reference": "Reference", "view_order": "View your order",
        "or_visit": "or", "visit_shop": "Visit our store",
        "footer": "If you have any questions, reply to this email or contact us at",
        "disclaimer": "Products are intended for research purposes only.",
        "ab_subject": "You left something in your cart 👀", "ab_title": "Your cart is waiting",
        "ab_body": "We saved your items. Complete your order in just a few clicks.",
        "ab_cta": "Complete my order", "qty": "pcs",
        "sh_subject": "Order {n} is on its way 🚚", "sh_title": "Your parcel is on its way", "sh_body": "The waybill for order {n} has been issued. Track the parcel with the courier or on your order page.", "sh_courier": "Courier",
        "dv_subject": "Order {n} has been delivered ✅", "dv_title": "Your parcel has been delivered", "dv_body": "Order {n} has been delivered. Thank you for choosing PurePeptide! If you have any questions, just reply to this email.",
        "sh_awb": "Waybill number", "sh_track": "Track the parcel", "sh_view": "View order", "sh_cod": "Amount due on delivery",
        "cx_subject": "Order {n} has been cancelled · PurePeptide", "cx_title": "Order cancelled",
        "cx_body": "Order {n} has been cancelled and will not be shipped. There is nothing to pay. If this was a mistake or you want to order again, just reply to this e-mail.", "cx_reason": "Reason",
        "pr_subject": "Payment received for order {n} · PurePeptide", "pr_title": "Payment confirmed", "pr_body": "We have received the payment for order {n}. We are preparing it for shipping and will let you know once it is on its way.",
    },
    "fr": {
        "order": "Commande", "subject_order": "Commande {n} · PurePeptide",
        "title": "Merci pour votre achat !", "hello": "Bonjour {name},",
        "body_ship": "Nous préparons votre commande pour l'expédition. Nous vous informerons dès son envoi.",
        "body_bank": "Vous recevrez un e-mail de confirmation dès la réception de votre paiement.",
        "summary": "Récapitulatif de la commande", "subtotal": "Sous-total", "discount": "Remise",
        "shipping": "Livraison", "total": "Total", "free": "Offert", "saved": "Vous avez économisé",
        "customer_info": "Informations client", "ship_addr": "Adresse de livraison",
        "delivery_method": "Mode de livraison", "payment": "Paiement",
        "cod": "Paiement à la livraison", "bank": "Virement bancaire",
        "bank_details": "Coordonnées bancaires", "holder": "Bénéficiaire", "iban": "IBAN",
        "bic": "BIC", "reference": "Référence", "view_order": "Voir votre commande",
        "or_visit": "ou", "visit_shop": "Visitez notre boutique",
        "footer": "Pour toute question, répondez à cet e-mail ou écrivez-nous à",
        "disclaimer": "Produits destinés uniquement à la recherche.",
        "ab_subject": "Vous avez oublié quelque chose dans votre panier 👀",
        "ab_title": "Votre panier vous attend",
        "ab_body": "Nous avons gardé vos articles. Finalisez votre commande en quelques clics.",
        "ab_cta": "Finaliser ma commande", "qty": "pcs",
        "sh_subject": "La commande {n} est en route 🚚", "sh_title": "Votre colis est en route", "sh_body": "Le bordereau de la commande {n} a été émis. Suivez le colis chez le transporteur ou sur la page de votre commande.", "sh_courier": "Transporteur",
        "dv_subject": "La commande {n} a été livrée ✅", "dv_title": "Votre colis a été livré", "dv_body": "La commande {n} a été livrée. Merci d'avoir choisi PurePeptide ! Pour toute question, répondez simplement à cet e-mail.",
        "sh_awb": "Numéro de suivi", "sh_track": "Suivre le colis", "sh_view": "Voir la commande", "sh_cod": "Montant à payer à la livraison",
        "cx_subject": "La commande {n} a été annulée · PurePeptide", "cx_title": "Commande annulée",
        "cx_body": "La commande {n} a été annulée et ne sera pas expédiée. Vous n'avez rien à payer. Si c'est une erreur ou si vous souhaitez commander à nouveau, répondez simplement à cet e-mail.", "cx_reason": "Motif",
        "pr_subject": "Paiement reçu pour la commande {n} · PurePeptide", "pr_title": "Paiement confirmé", "pr_body": "Nous avons reçu le paiement de la commande {n}. Nous la préparons pour l'expédition et vous informerons dès son départ.",
    },
    "de": {
        "order": "Bestellung", "subject_order": "Bestellung {n} · PurePeptide",
        "title": "Vielen Dank für Ihren Einkauf!", "hello": "Hallo {name},",
        "body_ship": "Wir bereiten Ihre Bestellung für den Versand vor. Wir informieren Sie, sobald sie verschickt wird.",
        "body_bank": "Sie erhalten eine Bestätigung per E-Mail, sobald Ihre Zahlung eingegangen ist.",
        "summary": "Bestellübersicht", "subtotal": "Zwischensumme", "discount": "Rabatt",
        "shipping": "Versand", "total": "Gesamt", "free": "Kostenlos", "saved": "Sie haben gespart",
        "customer_info": "Kundeninformationen", "ship_addr": "Lieferadresse",
        "delivery_method": "Versandart", "payment": "Zahlung",
        "cod": "Nachnahme", "bank": "Banküberweisung",
        "bank_details": "Bankverbindung", "holder": "Empfänger", "iban": "IBAN",
        "bic": "BIC", "reference": "Verwendungszweck", "view_order": "Bestellung ansehen",
        "or_visit": "oder", "visit_shop": "Unseren Shop besuchen",
        "footer": "Bei Fragen antworten Sie einfach auf diese E-Mail oder schreiben Sie an",
        "disclaimer": "Die Produkte sind ausschließlich für Forschungszwecke bestimmt.",
        "ab_subject": "Sie haben etwas im Warenkorb vergessen 👀",
        "ab_title": "Ihr Warenkorb wartet auf Sie",
        "ab_body": "Wir haben Ihre Artikel gespeichert. Schließen Sie Ihre Bestellung mit wenigen Klicks ab.",
        "ab_cta": "Bestellung abschließen", "qty": "Stk.",
        "sh_subject": "Bestellung {n} ist unterwegs 🚚", "sh_title": "Ihr Paket ist unterwegs", "sh_body": "Der Frachtbrief für Bestellung {n} wurde erstellt. Verfolgen Sie das Paket beim Kurier oder auf Ihrer Bestellseite.", "sh_courier": "Kurier",
        "dv_subject": "Bestellung {n} wurde zugestellt ✅", "dv_title": "Ihr Paket wurde zugestellt", "dv_body": "Bestellung {n} wurde zugestellt. Vielen Dank, dass Sie sich für PurePeptide entschieden haben! Bei Fragen antworten Sie einfach auf diese E-Mail.",
        "sh_awb": "Sendungsnummer", "sh_track": "Sendung verfolgen", "sh_view": "Bestellung ansehen", "sh_cod": "Bei Lieferung zu zahlender Betrag",
        "cx_subject": "Bestellung {n} wurde storniert · PurePeptide", "cx_title": "Bestellung storniert",
        "cx_body": "Bestellung {n} wurde storniert und wird nicht versandt. Es ist nichts zu bezahlen. Falls dies ein Versehen war oder Sie erneut bestellen möchten, antworten Sie einfach auf diese E-Mail.", "cx_reason": "Grund",
        "pr_subject": "Zahlung für Bestellung {n} erhalten · PurePeptide", "pr_title": "Zahlung bestätigt", "pr_body": "Wir haben die Zahlung für Bestellung {n} erhalten. Wir bereiten den Versand vor und melden uns, sobald das Paket unterwegs ist.",
    },
    "cz": {
        "order": "Objednávka", "subject_order": "Objednávka {n} · PurePeptide",
        "title": "Děkujeme za váš nákup!", "hello": "Dobrý den, {name},",
        "body_ship": "Připravujeme vaši objednávku k odeslání. Ozveme se, až bude vyexpedována.",
        "body_bank": "Potvrzení vám zašleme e-mailem, jakmile obdržíme vaši platbu.",
        "summary": "Přehled objednávky", "subtotal": "Mezisoučet", "discount": "Sleva",
        "shipping": "Doprava", "total": "Celkem", "free": "Zdarma", "saved": "Ušetřili jste",
        "customer_info": "Informace o zákazníkovi", "ship_addr": "Doručovací adresa",
        "delivery_method": "Způsob dopravy", "payment": "Platba",
        "cod": "Platba na dobírku", "bank": "Bankovní převod",
        "bank_details": "Údaje pro bankovní převod", "holder": "Příjemce", "iban": "IBAN",
        "bic": "BIC", "reference": "Variabilní symbol", "view_order": "Zobrazit objednávku",
        "or_visit": "nebo", "visit_shop": "Navštivte náš obchod",
        "footer": "Máte-li dotazy, odpovězte na tento e-mail nebo nám napište na",
        "disclaimer": "Produkty jsou určeny výhradně pro výzkumné účely.",
        "ab_subject": "Zapomněli jste něco v košíku 👀", "ab_title": "Váš košík na vás čeká",
        "ab_body": "Uložili jsme vaše položky. Dokončete objednávku na několik kliknutí.",
        "ab_cta": "Dokončit objednávku", "qty": "ks",
        "sh_subject": "Objednávka {n} je na cestě 🚚", "sh_title": "Váš balík je na cestě", "sh_body": "Přepravní štítek pro objednávku {n} byl vystaven. Sledujte balík u kurýra nebo na stránce objednávky.", "sh_courier": "Kurýr",
        "dv_subject": "Objednávka {n} byla doručena ✅", "dv_title": "Váš balík byl doručen", "dv_body": "Objednávka {n} byla doručena. Děkujeme, že jste si vybrali PurePeptide! V případě dotazů stačí odpovědět na tento e-mail.",
        "sh_awb": "Číslo zásilky", "sh_track": "Sledovat zásilku", "sh_view": "Zobrazit objednávku", "sh_cod": "Částka k úhradě při doručení",
        "cx_subject": "Objednávka {n} byla zrušena · PurePeptide", "cx_title": "Objednávka zrušena",
        "cx_body": "Objednávka {n} byla zrušena a nebude odeslána. Nic neplatíte. Pokud šlo o omyl nebo chcete objednat znovu, stačí odpovědět na tento e-mail.", "cx_reason": "Důvod",
        "pr_subject": "Platba za objednávku {n} přijata · PurePeptide", "pr_title": "Platba potvrzena", "pr_body": "Přijali jsme platbu za objednávku {n}. Připravujeme ji k odeslání a dáme vám vědět, až bude na cestě.",
    },
    "hu": {
        "order": "Megrendelés", "subject_order": "Megrendelés {n} · PurePeptide",
        "title": "Köszönjük a vásárlást!", "hello": "Kedves {name},",
        "body_ship": "Készítjük a csomagját a kiszállításra. Értesítjük, amint elindul.",
        "body_bank": "Visszaigazoló e-mailt küldünk, amint a fizetés beérkezik.",
        "summary": "Megrendelés összegzése", "subtotal": "Részösszeg", "discount": "Kedvezmény",
        "shipping": "Szállítás", "total": "Összesen", "free": "Ingyenes", "saved": "Megtakarítás",
        "customer_info": "Vásárlói adatok", "ship_addr": "Szállítási cím",
        "delivery_method": "Szállítási mód", "payment": "Fizetés",
        "cod": "Utánvét", "bank": "Banki átutalás",
        "bank_details": "Banki átutalás adatai", "holder": "Kedvezményezett", "iban": "IBAN",
        "bic": "BIC", "reference": "Közlemény", "view_order": "Megrendelés megtekintése",
        "or_visit": "vagy", "visit_shop": "Látogasson el az üzletünkbe",
        "footer": "Kérdés esetén válaszoljon erre az e-mailre, vagy írjon nekünk:",
        "disclaimer": "A termékek kizárólag kutatási célra készültek.",
        "ab_subject": "Valamit a kosárban hagyott 👀", "ab_title": "A kosara várja Önt",
        "ab_body": "Elmentettük a termékeit. Fejezze be a rendelést néhány kattintással.",
        "ab_cta": "Rendelés befejezése", "qty": "db",
        "sh_subject": "A {n} rendelés úton van 🚚", "sh_title": "Csomagja úton van", "sh_body": "A {n} rendelés fuvarlevele elkészült. Kövesse a csomagot a futárnál vagy a rendelés oldalán.", "sh_courier": "Futár",
        "dv_subject": "A {n} rendelés kézbesítve ✅", "dv_title": "Csomagját kézbesítettük", "dv_body": "A {n} rendelést kézbesítettük. Köszönjük, hogy a PurePeptide-ot választotta! Kérdés esetén válaszoljon erre az e-mailre.",
        "sh_awb": "Fuvarlevél száma", "sh_track": "Csomag követése", "sh_view": "Rendelés megtekintése", "sh_cod": "Átvételkor fizetendő összeg",
        "cx_subject": "A {n} megrendelést visszavontuk · PurePeptide", "cx_title": "Megrendelés visszavonva",
        "cx_body": "A {n} megrendelést visszavontuk, nem kerül kiszállításra. Nincs fizetendő összeg. Ha tévedés történt, vagy újra szeretne rendelni, csak válaszoljon erre az e-mailre.", "cx_reason": "Ok",
        "pr_subject": "A {n} megrendelés fizetése megérkezett · PurePeptide", "pr_title": "Fizetés megerősítve", "pr_body": "Megkaptuk a {n} megrendelés ellenértékét. Előkészítjük a csomagot, és jelezzük, amint elindult.",
    },
    "pl": {
        "order": "Zamówienie", "subject_order": "Zamówienie {n} · PurePeptide",
        "title": "Dziękujemy za zakup!", "hello": "Cześć {name},",
        "body_ship": "Przygotowujemy Twoje zamówienie do wysyłki. Powiadomimy Cię, gdy zostanie wysłane.",
        "body_bank": "Potwierdzenie otrzymasz e-mailem zaraz po zaksięgowaniu płatności.",
        "summary": "Podsumowanie zamówienia", "subtotal": "Suma częściowa", "discount": "Rabat",
        "shipping": "Dostawa", "total": "Razem", "free": "Bezpłatnie", "saved": "Zaoszczędziłeś",
        "customer_info": "Dane klienta", "ship_addr": "Adres dostawy",
        "delivery_method": "Sposób dostawy", "payment": "Płatność",
        "cod": "Płatność przy odbiorze", "bank": "Przelew bankowy",
        "bank_details": "Dane do przelewu", "holder": "Odbiorca", "iban": "IBAN",
        "bic": "BIC", "reference": "Tytuł przelewu", "view_order": "Zobacz zamówienie",
        "or_visit": "lub", "visit_shop": "Odwiedź nasz sklep",
        "footer": "W razie pytań odpowiedz na tę wiadomość lub napisz do nas na",
        "disclaimer": "Produkty przeznaczone wyłącznie do celów badawczych.",
        "ab_subject": "Zostawiłeś coś w koszyku 👀", "ab_title": "Twój koszyk czeka",
        "ab_body": "Zachowaliśmy Twoje produkty. Dokończ zamówienie w kilku kliknięciach.",
        "ab_cta": "Dokończ zamówienie", "qty": "szt.",
        "sh_subject": "Zamówienie {n} jest w drodze 🚚", "sh_title": "Twoja przesyłka jest w drodze", "sh_body": "List przewozowy dla zamówienia {n} został wystawiony. Śledź przesyłkę u kuriera lub na stronie zamówienia.", "sh_courier": "Kurier",
        "dv_subject": "Zamówienie {n} zostało dostarczone ✅", "dv_title": "Twoja przesyłka została dostarczona", "dv_body": "Zamówienie {n} zostało dostarczone. Dziękujemy za wybór PurePeptide! W razie pytań odpowiedz na tę wiadomość.",
        "sh_awb": "Numer listu przewozowego", "sh_track": "Śledź przesyłkę", "sh_view": "Zobacz zamówienie", "sh_cod": "Kwota do zapłaty przy odbiorze",
        "cx_subject": "Zamówienie {n} zostało anulowane · PurePeptide", "cx_title": "Zamówienie anulowane",
        "cx_body": "Zamówienie {n} zostało anulowane i nie zostanie wysłane. Nie masz nic do zapłaty. Jeśli to pomyłka lub chcesz zamówić ponownie, odpowiedz na tę wiadomość.", "cx_reason": "Powód",
        "pr_subject": "Otrzymaliśmy płatność za zamówienie {n} · PurePeptide", "pr_title": "Płatność potwierdzona", "pr_body": "Otrzymaliśmy płatność za zamówienie {n}. Przygotowujemy je do wysyłki i poinformujemy Cię, gdy ruszy.",
    },
    "sk": {
        "order": "Objednávka", "subject_order": "Objednávka {n} · PurePeptide",
        "title": "Ďakujeme za váš nákup!", "hello": "Dobrý deň, {name},",
        "body_ship": "Pripravujeme vašu objednávku na odoslanie. Ozveme sa, keď bude expedovaná.",
        "body_bank": "Potvrdenie vám pošleme e-mailom, len čo dostaneme vašu platbu.",
        "summary": "Prehľad objednávky", "subtotal": "Medzisúčet", "discount": "Zľava",
        "shipping": "Doprava", "total": "Celkom", "free": "Zdarma", "saved": "Ušetrili ste",
        "customer_info": "Informácie o zákazníkovi", "ship_addr": "Doručovacia adresa",
        "delivery_method": "Spôsob dopravy", "payment": "Platba",
        "cod": "Platba na dobierku", "bank": "Bankový prevod",
        "bank_details": "Údaje na bankový prevod", "holder": "Príjemca", "iban": "IBAN",
        "bic": "BIC", "reference": "Poznámka pre príjemcu", "view_order": "Zobraziť objednávku",
        "or_visit": "alebo", "visit_shop": "Navštívte náš obchod",
        "footer": "Ak máte otázky, odpovedzte na tento e-mail alebo nám napíšte na",
        "disclaimer": "Produkty sú určené výhradne na výskumné účely.",
        "ab_subject": "Zabudli ste niečo v košíku 👀", "ab_title": "Váš košík na vás čaká",
        "ab_body": "Uložili sme vaše položky. Dokončite objednávku na niekoľko klikov.",
        "ab_cta": "Dokončiť objednávku", "qty": "ks",
        "sh_subject": "Objednávka {n} je na ceste 🚚", "sh_title": "Váš balík je na ceste", "sh_body": "Prepravný štítok pre objednávku {n} bol vystavený. Sledujte balík u kuriéra alebo na stránke objednávky.", "sh_courier": "Kuriér",
        "dv_subject": "Objednávka {n} bola doručená ✅", "dv_title": "Váš balík bol doručený", "dv_body": "Objednávka {n} bola doručená. Ďakujeme, že ste si vybrali PurePeptide! V prípade otázok stačí odpovedať na tento e-mail.",
        "sh_awb": "Číslo zásielky", "sh_track": "Sledovať zásielku", "sh_view": "Zobraziť objednávku", "sh_cod": "Suma na úhradu pri doručení",
        "cx_subject": "Objednávka {n} bola zrušená · PurePeptide", "cx_title": "Objednávka zrušená",
        "cx_body": "Objednávka {n} bola zrušená a nebude odoslaná. Nič neplatíte. Ak išlo o omyl alebo chcete objednať znova, stačí odpovedať na tento e-mail.", "cx_reason": "Dôvod",
        "pr_subject": "Platba za objednávku {n} prijatá · PurePeptide", "pr_title": "Platba potvrdená", "pr_body": "Prijali sme platbu za objednávku {n}. Pripravujeme ju na odoslanie a dáme vám vedieť, keď bude na ceste.",
    },
    "si": {
        "order": "Naročilo", "subject_order": "Naročilo {n} · PurePeptide",
        "title": "Hvala za vaš nakup!", "hello": "Zdravo, {name},",
        "body_ship": "Vaše naročilo pripravljamo za odpremo. Obvestili vas bomo, ko bo poslano.",
        "body_bank": "Potrditev boste prejeli po e-pošti takoj, ko prispe vaše plačilo.",
        "summary": "Povzetek naročila", "subtotal": "Vmesni znesek", "discount": "Popust",
        "shipping": "Dostava", "total": "Skupaj", "free": "Brezplačno", "saved": "Prihranili ste",
        "customer_info": "Podatki o stranki", "ship_addr": "Naslov za dostavo",
        "delivery_method": "Način dostave", "payment": "Plačilo",
        "cod": "Plačilo po povzetju", "bank": "Bančno nakazilo",
        "bank_details": "Podatki za nakazilo", "holder": "Prejemnik", "iban": "IBAN",
        "bic": "BIC", "reference": "Sklic", "view_order": "Ogled naročila",
        "or_visit": "ali", "visit_shop": "Obiščite našo trgovino",
        "footer": "Če imate vprašanja, odgovorite na to sporočilo ali nam pišite na",
        "disclaimer": "Izdelki so namenjeni izključno raziskovalnim namenom.",
        "ab_subject": "V košarici ste nekaj pozabili 👀", "ab_title": "Vaša košarica vas čaka",
        "ab_body": "Shranili smo vaše izdelke. Zaključite naročilo z nekaj kliki.",
        "ab_cta": "Zaključi naročilo", "qty": "kos",
        "sh_subject": "Naročilo {n} je na poti 🚚", "sh_title": "Vaš paket je na poti", "sh_body": "Tovorni list za naročilo {n} je izdan. Paket spremljajte pri kurirju ali na strani naročila.", "sh_courier": "Kurir",
        "dv_subject": "Naročilo {n} je dostavljeno ✅", "dv_title": "Vaš paket je dostavljen", "dv_body": "Naročilo {n} je dostavljeno. Hvala, ker ste izbrali PurePeptide! Če imate vprašanja, odgovorite na to e-pošto.",
        "sh_awb": "Številka pošiljke", "sh_track": "Spremljaj pošiljko", "sh_view": "Ogled naročila", "sh_cod": "Znesek za plačilo ob dostavi",
        "cx_subject": "Naročilo {n} je preklicano · PurePeptide", "cx_title": "Naročilo preklicano",
        "cx_body": "Naročilo {n} je preklicano in ne bo odposlano. Ničesar ni treba plačati. Če je šlo za pomoto ali želite naročiti znova, samo odgovorite na to sporočilo.", "cx_reason": "Razlog",
        "pr_subject": "Plačilo za naročilo {n} je prejeto · PurePeptide", "pr_title": "Plačilo potrjeno", "pr_body": "Prejeli smo plačilo za naročilo {n}. Pripravljamo ga za odpremo in vas obvestimo, ko bo na poti.",
    },
    "gr": {
        "order": "Παραγγελία", "subject_order": "Παραγγελία {n} · PurePeptide",
        "title": "Σας ευχαριστούμε για την αγορά σας!", "hello": "Γεια σας, {name},",
        "body_ship": "Ετοιμάζουμε την παραγγελία σας για αποστολή. Θα σας ενημερώσουμε μόλις σταλεί.",
        "body_bank": "Θα λάβετε email επιβεβαίωσης μόλις εισπραχθεί η πληρωμή σας.",
        "summary": "Σύνοψη παραγγελίας", "subtotal": "Υποσύνολο", "discount": "Έκπτωση",
        "shipping": "Αποστολή", "total": "Σύνολο", "free": "Δωρεάν", "saved": "Κερδίσατε",
        "customer_info": "Στοιχεία πελάτη", "ship_addr": "Διεύθυνση αποστολής",
        "delivery_method": "Τρόπος αποστολής", "payment": "Πληρωμή",
        "cod": "Αντικαταβολή", "bank": "Τραπεζική μεταφορά",
        "bank_details": "Στοιχεία τραπεζικής μεταφοράς", "holder": "Δικαιούχος", "iban": "IBAN",
        "bic": "BIC", "reference": "Αιτιολογία", "view_order": "Δείτε την παραγγελία σας",
        "or_visit": "ή", "visit_shop": "Επισκεφθείτε το κατάστημά μας",
        "footer": "Για οποιαδήποτε ερώτηση, απαντήστε σε αυτό το email ή γράψτε μας στο",
        "disclaimer": "Τα προϊόντα προορίζονται αποκλειστικά για ερευνητικούς σκοπούς.",
        "ab_subject": "Ξεχάσατε κάτι στο καλάθι σας 👀", "ab_title": "Το καλάθι σας σας περιμένει",
        "ab_body": "Κρατήσαμε τα προϊόντα σας. Ολοκληρώστε την παραγγελία με λίγα κλικ.",
        "ab_cta": "Ολοκλήρωση παραγγελίας", "qty": "τεμ.",
        "sh_subject": "Η παραγγελία {n} είναι καθ' οδόν 🚚", "sh_title": "Το δέμα σας είναι καθ' οδόν", "sh_body": "Η φορτωτική για την παραγγελία {n} εκδόθηκε. Παρακολουθήστε το δέμα στον courier ή στη σελίδα της παραγγελίας.", "sh_courier": "Courier",
        "dv_subject": "Η παραγγελία {n} παραδόθηκε ✅", "dv_title": "Το δέμα σας παραδόθηκε", "dv_body": "Η παραγγελία {n} παραδόθηκε. Σας ευχαριστούμε που επιλέξατε την PurePeptide! Για ερωτήσεις, απαντήστε σε αυτό το e-mail.",
        "sh_awb": "Αριθμός φορτωτικής", "sh_track": "Παρακολούθηση δέματος", "sh_view": "Προβολή παραγγελίας", "sh_cod": "Ποσό πληρωμής κατά την παράδοση",
        "cx_subject": "Η παραγγελία {n} ακυρώθηκε · PurePeptide", "cx_title": "Η παραγγελία ακυρώθηκε",
        "cx_body": "Η παραγγελία {n} ακυρώθηκε και δεν θα αποσταλεί. Δεν οφείλετε τίποτα. Αν έγινε από λάθος ή θέλετε να παραγγείλετε ξανά, απαντήστε σε αυτό το e-mail.", "cx_reason": "Αιτία",
        "pr_subject": "Λάβαμε την πληρωμή για την παραγγελία {n} · PurePeptide", "pr_title": "Η πληρωμή επιβεβαιώθηκε", "pr_body": "Λάβαμε την πληρωμή για την παραγγελία {n}. Την προετοιμάζουμε για αποστολή και θα σας ενημερώσουμε μόλις ξεκινήσει.",
    },
    "ro": {
        "order": "Comandă", "subject_order": "Comanda {n} · PurePeptide",
        "title": "Vă mulțumim pentru achiziție!", "hello": "Bună, {name},",
        "body_ship": "Pregătim comanda pentru expediere. Vă anunțăm imediat ce este trimisă.",
        "body_bank": "Veți primi un e-mail de confirmare imediat ce plata este înregistrată.",
        "summary": "Sumarul comenzii", "subtotal": "Subtotal", "discount": "Reducere",
        "shipping": "Livrare", "total": "Total", "free": "Gratuit", "saved": "Ați economisit",
        "customer_info": "Informații client", "ship_addr": "Adresă de livrare",
        "delivery_method": "Metodă de livrare", "payment": "Plată",
        "cod": "Plată ramburs la livrare", "bank": "Transfer bancar",
        "bank_details": "Detalii transfer bancar", "holder": "Beneficiar", "iban": "IBAN",
        "bic": "BIC", "reference": "Referință", "view_order": "Vezi comanda",
        "or_visit": "sau", "visit_shop": "Vizitați magazinul nostru",
        "footer": "Dacă aveți întrebări, răspundeți la acest e-mail sau scrieți-ne la",
        "disclaimer": "Produsele sunt destinate exclusiv scopurilor de cercetare.",
        "ab_subject": "Ați uitat ceva în coș 👀", "ab_title": "Coșul dvs. vă așteaptă",
        "ab_body": "Am păstrat produsele dvs. Finalizați comanda în doar câteva clicuri.",
        "ab_cta": "Finalizează comanda", "qty": "buc",
        "sh_subject": "Comanda {n} este pe drum 🚚", "sh_title": "Coletul dvs. este pe drum", "sh_body": "AWB-ul pentru comanda {n} a fost emis. Urmăriți coletul la curier sau în pagina comenzii.", "sh_courier": "Curier",
        "dv_subject": "Comanda {n} a fost livrată ✅", "dv_title": "Coletul dvs. a fost livrat", "dv_body": "Comanda {n} a fost livrată. Vă mulțumim că ați ales PurePeptide! Pentru întrebări, răspundeți la acest e-mail.",
        "sh_awb": "Număr AWB", "sh_track": "Urmărește coletul", "sh_view": "Vezi comanda", "sh_cod": "Sumă de plată la livrare",
        "cx_subject": "Comanda {n} a fost anulată · PurePeptide", "cx_title": "Comandă anulată",
        "cx_body": "Comanda {n} a fost anulată și nu va fi expediată. Nu aveți nimic de plată. Dacă a fost o greșeală sau doriți să comandați din nou, răspundeți la acest e-mail.", "cx_reason": "Motiv",
        "pr_subject": "Plata pentru comanda {n} a fost primită · PurePeptide", "pr_title": "Plată confirmată", "pr_body": "Am primit plata pentru comanda {n}. O pregătim pentru expediere și vă anunțăm imediat ce pleacă.",
    },
}


# Public tracking page (order number + phone) — merged in so every locale has it.
for _loc, _cta in {
    "bg": "Проследи поръчката", "en": "Track your order", "fr": "Suivre ma commande",
    "de": "Bestellung verfolgen", "cz": "Sledovat objednávku", "hu": "Megrendelés követése",
    "pl": "Śledź zamówienie", "sk": "Sledovať objednávku", "si": "Sledi naročilu",
    "gr": "Παρακολούθηση παραγγελίας", "ro": "Urmărește comanda",
}.items():
    T.setdefault(_loc, {})["track_cta"] = _cta



def tr(locale: str, key: str, **kw) -> str:
    loc = (locale or "bg").lower()
    table = T.get(loc) or T["bg"]
    value = table.get(key) or T["bg"].get(key, key)
    return value.format(**kw) if kw else value


def base_url(locale: str) -> str:
    override = (os.environ.get("PUBLIC_SITE_URL") or "").strip().rstrip("/")
    if override:
        return override
    return LOCALE_ORIGIN.get((locale or "bg").lower(), LOCALE_ORIGIN["bg"])


def _abs(url: str, base: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return f"{base}{url if url.startswith('/') else '/' + url}"


SYMBOLS = {"EUR": "€", "RON": "RON", "PLN": "zł", "CZK": "Kč", "HUF": "Ft", "BGN": "лв."}

EUR_TRANSFER_NOTE = {
    "bg": "Сума за превод в евро", "en": "Amount to transfer in EUR", "fr": "Montant à virer en EUR",
    "de": "Überweisungsbetrag in EUR", "cz": "Částka k převodu v EUR", "hu": "Átutalandó összeg EUR-ban",
    "pl": "Kwota przelewu w EUR", "sk": "Suma na prevod v EUR", "si": "Znesek za nakazilo v EUR",
    "gr": "Ποσό μεταφοράς σε EUR", "ro": "Suma de transferat în EUR",
}


def _money(v: Any, cur: str = "EUR") -> str:
    """Same layout as the storefront (Intl, 0 decimals for local currencies): 1 299 Kč, 638 RON."""
    code = (cur or "EUR").upper()
    symbol = SYMBOLS.get(code, code)
    try:
        amount = float(v or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if code == "EUR":
        return f"€{amount:.2f}"
    return f"{amount:,.0f}\u00a0{symbol}".replace(",", "\u00a0")


def localize_order(order: Dict[str, Any], fx: Dict[str, Any]) -> Dict[str, Any]:
    """Re-derive the local-currency mirror of an order for another storefront (email previews)."""
    from currency import nice_price, order_amounts

    code = str(fx.get("currency") or "EUR").upper()
    if code == str(order.get("currency") or "EUR").upper():
        return order
    items = [dict(i) for i in order.get("items") or []]
    if code == "EUR":
        for it in items:
            it.pop("price_orig", None)
        out = {**order, "items": items, "currency": "EUR", "currency_rate": 1.0}
        for k in ("subtotal_orig", "discount_orig", "shipping_orig", "total_orig"):
            out.pop(k, None)
        return out
    rate = float(fx.get("rate") or 1.0)
    totals = {k: float(order.get(k) or 0) for k in ("subtotal_eur", "discount_eur", "shipping_eur", "total_eur")}
    local = order_amounts(items, totals, order.get("discount") or {}, code, rate)
    for it, price in zip(items, local.pop("item_prices", [])):
        it["price_orig"] = price
    for it in items:
        it.setdefault("price_orig", nice_price(it.get("price_eur"), code, rate))
    return {**order, "items": items, **local}


def _money_of(order: Dict[str, Any]):
    """Format in the currency the order was placed in — EUR orders keep the euro layout."""
    code = str(order.get("currency") or "EUR").upper()
    if code == "EUR":
        return lambda eur, orig=None: _money(eur, "EUR")
    return lambda eur, orig=None: _money(orig if orig is not None else eur, code)


def seller_lines(settings: Optional[Dict[str, Any]] = None) -> str:
    """Company details for invoices — name, registration number, VAT and address, from the settings."""
    s = settings or {}
    parts = [str(s.get("company_name") or "").strip()]
    if s.get("company_eik"):
        parts.append(f'ЕИК/UIC {str(s["company_eik"]).strip()}')
    if s.get("company_vat"):
        parts.append(f'ДДС/VAT {str(s["company_vat"]).strip()}')
    head = " · ".join(p for p in parts if p)
    address = str(s.get("company_address") or "").strip()
    if not head and not address:
        return ""
    return "<br>".join(x for x in [head, address] if x)


def _shell(locale: str, order_label: str, title: str, content: str, contact_email: str,
           seller: str = "") -> str:
    base = base_url(locale)
    return f"""<!doctype html>
<html lang="{locale}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#f4f6f8;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:26px 10px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
 style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
 box-shadow:0 12px 34px rgba(15,23,42,.08);">
  <tr><td style="padding:22px 28px 14px;border-bottom:1px solid #eef2f6;">
    <table role="presentation" width="100%"><tr>
      <td><a href="{base}" style="text-decoration:none;color:{DARK};font-size:19px;font-weight:700;
        letter-spacing:-.3px;"><img src="{base}/logo-header.png" alt="PurePeptide" height="26"
        style="height:26px;display:block;border:0;"></a></td>
      <td align="right" style="color:#94a3b8;font-size:12px;font-weight:600;">{order_label}</td>
    </tr></table>
  </td></tr>
  {content}
  <tr><td style="padding:20px 28px;background:{DARK};color:#94a3b8;font-size:11px;line-height:1.7;">
    {tr(locale, 'footer')} <a href="mailto:{contact_email}" style="color:#cbd5e1;">{contact_email}</a><br>
    {tr(locale, 'disclaimer')}
    {f'<br><br><span style="color:#64748b;">{seller}</span>' if seller else ''}
  </td></tr>
</table></td></tr></table></body></html>"""


def _lines(items: List[Dict[str, Any]], locale: str, base: str, money=None) -> str:
    money = money or (lambda eur, orig=None: _money(eur))
    rows = []
    for it in items or []:
        img = _abs(it.get("image") or "", base)
        thumb = (f'<img src="{img}" width="56" height="56" alt="" '
                 f'style="border-radius:10px;border:1px solid #eef2f6;object-fit:cover;">') if img else ""
        qty = int(it.get("quantity") or 1)
        price = money(float(it.get("price_eur") or 0) * qty,
                      float(it["price_orig"]) * qty if it.get("price_orig") is not None else None)
        rows.append(
            f'<tr><td width="72" style="padding:12px 0;border-bottom:1px solid #f1f5f9;">{thumb}</td>'
            f'<td style="padding:12px 0;border-bottom:1px solid #f1f5f9;font-size:14px;color:{DARK};">'
            f'<strong>{it.get("title", "")}</strong><br>'
            f'<span style="color:#64748b;font-size:12px;">{it.get("variant_name", "")} · '
            f'{it.get("quantity", 1)} {tr(locale, "qty")}</span></td>'
            f'<td align="right" style="padding:12px 0;border-bottom:1px solid #f1f5f9;font-size:14px;'
            f'color:{DARK};white-space:nowrap;"><strong>{price}</strong></td></tr>'
        )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _sum_row(label: str, value: str, strong: bool = False) -> str:
    weight = "700" if strong else "400"
    size = "16px" if strong else "14px"
    return (f'<tr><td style="padding:5px 0;font-size:{size};color:#475569;">{label}</td>'
            f'<td align="right" style="padding:5px 0;font-size:{size};color:{DARK};'
            f'font-weight:{weight};white-space:nowrap;">{value}</td></tr>')


def _button(url: str, label: str) -> str:
    return (f'<a href="{url}" style="display:inline-block;background:{BRAND};color:#fff;'
            f'text-decoration:none;font-size:15px;font-weight:600;padding:13px 26px;'
            f'border-radius:999px;">{label}</a>')


def render_order(order: Dict[str, Any], bank: Optional[Dict[str, Any]], locale: str,
                 contact_email: str, seller: str = "") -> tuple:
    loc = (locale or order.get("locale") or "bg").lower()
    base = base_url(loc)
    delivery = order.get("delivery") or {}
    ship = order.get("shipping") or {}
    pay_key = order.get("payment_method") or "cod"
    intro = tr(loc, "body_bank") if pay_key == "bank_transfer" else tr(loc, "body_ship")
    order_url = f"{base}/checkout/success/{order.get('id')}"
    money = _money_of(order)

    summary = [_sum_row(tr(loc, "subtotal"), money(order.get("subtotal_eur"), order.get("subtotal_orig")))]
    if float(order.get("discount_eur") or 0) > 0:
        summary.append(_sum_row(tr(loc, "discount"),
                                f"− {money(order.get('discount_eur'), order.get('discount_orig'))}"))
    ship_cost = float(order.get("shipping_eur") or 0)
    summary.append(_sum_row(
        f"{tr(loc, 'shipping')}{' · ' + delivery.get('provider_name') if delivery.get('provider_name') else ''}",
        money(ship_cost, order.get("shipping_orig")) if ship_cost else tr(loc, "free")))
    summary.append(_sum_row(tr(loc, "total"), money(order.get("total_eur"), order.get("total_orig")),
                            strong=True))

    office = (delivery.get("office") or {})
    addr_html = "<br>".join(x for x in [
        ship.get("full_name") or order.get("customer_name") or "",
        office.get("name") or ship.get("line1") or "",
        f'{ship.get("postal_code", "")} {ship.get("city", "")}'.strip(),
        ship.get("country") or "",
        order.get("customer_phone") or "",
    ] if x)

    bank_block = ""
    if pay_key == "bank_transfer" and bank:
        bank_block = (
            f'<tr><td style="padding:0 28px 22px;">'
            f'<table role="presentation" width="100%" style="background:#f8fafc;border:1px solid #eef2f6;'
            f'border-radius:12px;padding:14px 16px;font-size:13px;color:#334155;">'
            f'<tr><td colspan="2" style="padding-bottom:8px;font-weight:700;color:{DARK};">'
            f'{tr(loc, "bank_details")}</td></tr>'
            f'<tr><td>{bank.get("name", "")}</td><td align="right">{tr(loc, "holder")}: '
            f'<strong>{bank.get("holder", "")}</strong></td></tr>'
            f'<tr><td>{tr(loc, "iban")}: <strong>{bank.get("iban", "")}</strong></td>'
            f'<td align="right">{tr(loc, "bic")}: <strong>{bank.get("bic", "")}</strong></td></tr>'
            f'<tr><td colspan="2" style="padding-top:6px;">{tr(loc, "reference")}: '
            f'<strong>{bank.get("reference") or order.get("order_number", "")}</strong></td></tr>'
            # the IBAN is a euro account — a local-currency order still transfers the EUR amount
            + (f'<tr><td colspan="2" style="padding-top:6px;color:#64748b;">'
               f'{EUR_TRANSFER_NOTE.get(loc, EUR_TRANSFER_NOTE["en"])}: '
               f'<strong>{_money(order.get("total_eur"), "EUR")}</strong></td></tr>'
               if str(order.get("currency") or "EUR").upper() != "EUR" else "")
            + f'</table></td></tr>'
        )

    content = f"""
  <tr><td style="padding:26px 28px 6px;">
    <h1 style="margin:0 0 8px;font-size:24px;line-height:1.25;color:{DARK};">{tr(loc, 'title')}</h1>
    <p style="margin:0 0 6px;font-size:14px;color:#475569;">
      {tr(loc, 'hello', name=(order.get('customer_name') or '').split(' ')[0])}</p>
    <p style="margin:0 0 18px;font-size:14px;color:#475569;line-height:1.7;">{intro}</p>
    {_button(order_url, tr(loc, 'view_order'))}
    <p style="margin:12px 0 0;font-size:12px;color:#94a3b8;">{tr(loc, 'or_visit')}
      <a href="{base}" style="color:{BRAND};">{tr(loc, 'visit_shop')}</a>
      &nbsp;·&nbsp;<a href="{base}/track?n={order.get('order_number', '')}" style="color:{BRAND};">{tr(loc, 'track_cta')}</a></p>
  </td></tr>
  <tr><td style="padding:22px 28px 0;">
    <h2 style="margin:0 0 4px;font-size:15px;color:{DARK};">{tr(loc, 'summary')}</h2>
    {_lines(order.get('items') or [], loc, base, money)}
    <table role="presentation" width="100%" style="margin-top:12px;">{''.join(summary)}</table>
  </td></tr>
  {bank_block}
  <tr><td style="padding:18px 28px 26px;border-top:1px solid #eef2f6;">
    <h2 style="margin:0 0 12px;font-size:15px;color:{DARK};">{tr(loc, 'customer_info')}</h2>
    <table role="presentation" width="100%" style="font-size:13px;color:#475569;line-height:1.7;">
      <tr valign="top">
        <td width="50%"><strong style="color:{DARK};">{tr(loc, 'ship_addr')}</strong><br>{addr_html}</td>
        <td width="50%"><strong style="color:{DARK};">{tr(loc, 'payment')}</strong><br>
          {tr(loc, 'bank') if pay_key == 'bank_transfer' else tr(loc, 'cod')}<br><br>
          <strong style="color:{DARK};">{tr(loc, 'delivery_method')}</strong><br>
          {delivery.get('label') or order.get('shipping_method') or ''}
          {('<br>' + office.get('address')) if office.get('address') else ''}
        </td>
      </tr>
    </table>
  </td></tr>"""

    order_label = f"{tr(loc, 'order')} {order.get('order_number', '')}"
    subject = tr(loc, "subject_order", n=order.get("order_number", ""))
    return subject, _shell(loc, order_label, subject, content, contact_email, seller)


def render_abandoned(cart: Dict[str, Any], locale: str, contact_email: str, seller: str = "",
                     discount_code: str = "", fx: Optional[Dict[str, Any]] = None) -> tuple:
    loc = (locale or cart.get("locale") or "bg").lower()
    base = base_url(loc)
    items = [dict(i) for i in cart.get("items") or []]
    code = str((fx or {}).get("currency") or "EUR").upper()
    if code != "EUR":
        from currency import nice_price

        rate = float((fx or {}).get("rate") or 1.0)
        for it in items:
            it["price_orig"] = nice_price(it.get("price_eur"), code, rate)
        subtotal = sum(float(i["price_orig"]) * int(i.get("quantity") or 1) for i in items)
    else:
        subtotal = sum(float(i.get("price_eur") or 0) * int(i.get("quantity") or 1) for i in items)
    money = _money_of({"currency": code})
    promo = ""
    if discount_code:
        promo = (f'<p style="margin:14px 0 0;font-size:13px;color:#475569;">'
                 f'<span style="background:#fff1ef;border:1px dashed {BRAND};color:{BRAND};'
                 f'padding:6px 12px;border-radius:8px;font-weight:700;">{discount_code}</span></p>')
    content = f"""
  <tr><td style="padding:26px 28px 6px;">
    <h1 style="margin:0 0 8px;font-size:24px;line-height:1.25;color:{DARK};">{tr(loc, 'ab_title')}</h1>
    <p style="margin:0 0 6px;font-size:14px;color:#475569;">
      {tr(loc, 'hello', name=(cart.get('customer_name') or '').split(' ')[0])}</p>
    <p style="margin:0 0 18px;font-size:14px;color:#475569;line-height:1.7;">{tr(loc, 'ab_body')}</p>
    {_button(f"{base}/cart", tr(loc, 'ab_cta'))}
    {promo}
  </td></tr>
  <tr><td style="padding:22px 28px 26px;">
    {_lines(items, loc, base, money)}
    <table role="presentation" width="100%" style="margin-top:12px;">
      {_sum_row(tr(loc, 'subtotal'), money(subtotal, subtotal), strong=True)}
    </table>
  </td></tr>"""
    subject = tr(loc, "ab_subject")
    return subject, _shell(loc, "", subject, content, contact_email, seller)


# ---------- admin notifications (always Bulgarian) ----------
def _admin_shell(badge: str, title: str, content: str, cta_url: str = "", cta_label: str = "") -> str:
    base = base_url("bg")
    cta = (f'<tr><td style="padding:0 28px 24px;">{_button(cta_url, cta_label)}</td></tr>'
           if cta_url and cta_label else "")
    return f"""<!doctype html>
<html lang="bg"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#0b1220;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b1220;padding:26px 10px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
 style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <tr><td style="padding:20px 28px;background:{DARK};">
    <table role="presentation" width="100%"><tr>
      <td><img src="{base}/logo-white.svg" alt="PurePeptide" height="24"
        style="height:24px;display:block;border:0;"></td>
      <td align="right"><span style="background:{BRAND};color:#fff;font-size:11px;font-weight:700;
        letter-spacing:.6px;padding:5px 11px;border-radius:999px;">{badge}</span></td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:24px 28px 4px;">
    <h1 style="margin:0 0 14px;font-size:21px;line-height:1.3;color:{DARK};">{title}</h1>
  </td></tr>
  {content}
  {cta}
  <tr><td style="padding:16px 28px;background:#f8fafc;color:#94a3b8;font-size:11px;line-height:1.6;
    border-top:1px solid #eef2f6;">PurePeptide · автоматично известие от системата</td></tr>
</table></td></tr></table></body></html>"""


def _kv_table(rows: List[tuple]) -> str:
    body = "".join(
        f'<tr><td width="150" style="padding:5px 0;font-size:13px;color:#94a3b8;">{k}</td>'
        f'<td style="padding:5px 0;font-size:13px;color:{DARK};font-weight:600;">{v}</td></tr>'
        for k, v in rows if v
    )
    return f'<table role="presentation" width="100%">{body}</table>'


def render_admin_order(order: Dict[str, Any]) -> tuple:
    base = base_url("bg")
    delivery = order.get("delivery") or {}
    office = delivery.get("office") or {}
    ship = order.get("shipping") or {}
    pay = "Банков превод" if order.get("payment_method") == "bank_transfer" else "Наложен платеж"
    money = _money_of(order)
    total = money(order.get("total_eur"), order.get("total_orig"))
    if str(order.get("currency") or "EUR").upper() != "EUR":
        total = f'{total} <span style="color:#94a3b8;font-size:13px;">({_money(order.get("total_eur"), "EUR")})</span>'
    rows = [
        ("Клиент", order.get("customer_name") or ""),
        ("Имейл", f'<a href="mailto:{order.get("customer_email", "")}" style="color:{BRAND};">'
                  f'{order.get("customer_email", "")}</a>'),
        ("Телефон", f'<a href="tel:{order.get("customer_phone", "")}" style="color:{BRAND};">'
                    f'{order.get("customer_phone", "")}</a>'),
        ("Плащане", pay),
        ("Доставка", delivery.get("label") or order.get("shipping_method") or ""),
        ("Офис / адрес", office.get("name") or ship.get("line1") or ""),
        ("Град", f'{ship.get("postal_code", "")} {ship.get("city", "")} · {ship.get("country", "")}'.strip()),
        ("Език", (order.get("locale") or "bg").upper()),
    ]
    content = f"""
  <tr><td style="padding:0 28px;">
    <table role="presentation" width="100%" style="background:#f8fafc;border:1px solid #eef2f6;
      border-radius:12px;"><tr>
      <td style="padding:14px 16px;font-size:13px;color:#64748b;">Сума на поръчката</td>
      <td align="right" style="padding:14px 16px;font-size:22px;font-weight:700;color:{DARK};">{total}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:18px 28px 0;">{_kv_table(rows)}</td></tr>
  <tr><td style="padding:16px 28px 20px;">
    {_lines(order.get('items') or [], 'bg', base, money)}
  </td></tr>"""
    subject = f"Нова поръчка {order.get('order_number', '')} · {money(order.get('total_eur'), order.get('total_orig'))}"
    html = _admin_shell("НОВА ПОРЪЧКА", f"Поръчка {order.get('order_number', '')}", content,
                        f"{base}/admin/orders/{order.get('id')}", "Отвори в админ панела")
    return subject, html


def render_admin_contact(msg: Dict[str, Any]) -> tuple:
    base = base_url("bg")
    rows = [
        ("Име", msg.get("name") or ""),
        ("Имейл", f'<a href="mailto:{msg.get("email", "")}" style="color:{BRAND};">{msg.get("email", "")}</a>'),
        ("Телефон", msg.get("phone") or "—"),
        ("Език", (msg.get("locale") or "bg").upper()),
    ]
    content = f"""
  <tr><td style="padding:0 28px;">{_kv_table(rows)}</td></tr>
  <tr><td style="padding:16px 28px 22px;">
    <div style="background:#f8fafc;border:1px solid #eef2f6;border-radius:12px;padding:14px 16px;
      font-size:14px;line-height:1.7;color:#334155;white-space:pre-line;">{msg.get('message', '')}</div>
  </td></tr>"""
    subject = f"Ново запитване от {msg.get('name', '')}"
    html = _admin_shell("ЗАПИТВАНЕ", "Ново запитване от сайта", content,
                        f"{base}/admin/messages", "Отвори съобщенията")
    return subject, html


def render_admin_note(badge: str, title: str, body_html: str, cta_url: str = "",
                      cta_label: str = "") -> str:
    """Simple branded admin notice (test emails, system alerts)."""
    content = (f'<tr><td style="padding:0 28px 22px;font-size:14px;color:#475569;line-height:1.7;">'
               f'{body_html}</td></tr>')
    return _admin_shell(badge, title, content, cta_url, cta_label)


def render_shipment(order: Dict[str, Any], locale: str, contact_email: str, seller: str = "") -> tuple:
    """Waybill issued: courier, number, tracking link and the order page — in the customer's language."""
    loc = (locale or order.get("locale") or "bg").lower()
    base = base_url(loc)
    sh = order.get("shipment") or {}
    n = order.get("order_number", "")
    money = _money_of(order)
    rows = [(tr(loc, "sh_courier"), sh.get("courier") or "NextLevel"), (tr(loc, "sh_awb"), sh.get("awb", ""))]
    if sh.get("courier_awb") and sh.get("courier_awb") != sh.get("awb"):
        rows.append((tr(loc, "sh_courier") + " №", sh["courier_awb"]))
    if order.get("payment_method") == "cod":
        rows.append((tr(loc, "sh_cod"), money(order.get("total_eur"), order.get("total_orig"))))
    table = "".join(
        f'<tr><td style="padding:6px 0;color:#64748b;">{k}</td>'
        f'<td style="padding:6px 0;text-align:right;font-weight:700;">{v}</td></tr>' for k, v in rows)
    buttons = ""
    if sh.get("tracking_link"):
        buttons += _button(sh["tracking_link"], tr(loc, "sh_track"))
    buttons += _button(f"{base}/checkout/success/{order.get('id', '')}", tr(loc, "sh_view"))
    content = f"""
  <tr><td style="padding:26px 28px 6px;">
    <p style="margin:0 0 8px;font-size:15px;color:#0f172a;">{tr(loc, 'hello', name=order.get('customer_name', ''))}</p>
    <p style="margin:0;font-size:14px;line-height:1.6;color:#334155;">{tr(loc, 'sh_body', n=n)}</p>
  </td></tr>
  <tr><td style="padding:14px 28px 6px;">
    <table role="presentation" width="100%" style="font-size:14px;border-top:1px solid #e2e8f0;">{table}</table>
  </td></tr>
  <tr><td style="padding:10px 28px 28px;">{buttons}</td></tr>"""
    subject = tr(loc, "sh_subject", n=n)
    return subject, _shell(loc, f"{tr(loc, 'order')} {n}", tr(loc, "sh_title"), content, contact_email, seller)


def render_delivered(order: Dict[str, Any], locale: str, contact_email: str, seller: str = "") -> tuple:
    """Courier confirmed delivery: a short thank-you with the order link."""
    loc = (locale or order.get("locale") or "bg").lower()
    base = base_url(loc)
    n = order.get("order_number", "")
    sh = order.get("shipment") or {}
    rows = [(tr(loc, "sh_courier"), sh.get("courier") or "NextLevel"), (tr(loc, "sh_awb"), sh.get("awb", ""))]
    table = "".join(
        f'<tr><td style="padding:6px 0;color:#64748b;">{k}</td>'
        f'<td style="padding:6px 0;text-align:right;font-weight:700;">{v}</td></tr>' for k, v in rows if v)
    content = f"""
  <tr><td style="padding:26px 28px 6px;">
    <p style="margin:0 0 8px;font-size:15px;color:#0f172a;">{tr(loc, 'hello', name=order.get('customer_name', ''))}</p>
    <p style="margin:0;font-size:14px;line-height:1.6;color:#334155;">{tr(loc, 'dv_body', n=n)}</p>
  </td></tr>
  <tr><td style="padding:14px 28px 6px;">
    <table role="presentation" width="100%" style="font-size:14px;border-top:1px solid #e2e8f0;">{table}</table>
  </td></tr>
  <tr><td style="padding:10px 28px 28px;">{_button(f"{base}/checkout/success/{order.get('id', '')}", tr(loc, 'sh_view'))}</td></tr>"""
    return tr(loc, "dv_subject", n=n), _shell(loc, f"{tr(loc, 'order')} {n}", tr(loc, "dv_title"), content, contact_email, seller)


def render_cancelled(order: Dict[str, Any], locale: str, contact_email: str, reason: str = "", seller: str = "") -> tuple:
    """The order was cancelled by the customer or by the shop — nothing left to pay."""
    loc = (locale or order.get("locale") or "bg").lower()
    n = order.get("order_number", "")
    rows = [(tr(loc, "cx_reason"), reason)] if reason else []
    table = "".join(
        f'<tr><td style="padding:6px 0;color:#64748b;">{k}</td>'
        f'<td style="padding:6px 0;text-align:right;font-weight:700;">{v}</td></tr>' for k, v in rows)
    content = f"""
  <tr><td style="padding:26px 28px 6px;">
    <p style="margin:0 0 8px;font-size:15px;color:#0f172a;">{tr(loc, 'hello', name=order.get('customer_name', ''))}</p>
    <p style="margin:0;font-size:14px;line-height:1.6;color:#334155;">{tr(loc, 'cx_body', n=n)}</p>
  </td></tr>""" + (f"""
  <tr><td style="padding:14px 28px 22px;">
    <table role="presentation" width="100%" style="font-size:14px;border-top:1px solid #e2e8f0;">{table}</table>
  </td></tr>""" if table else """
  <tr><td style="padding:0 28px 22px;"></td></tr>""")
    return tr(loc, "cx_subject", n=n), _shell(loc, f"{tr(loc, 'order')} {n}", tr(loc, "cx_title"), content, contact_email, seller)


def render_payment_received(order: Dict[str, Any], locale: str, contact_email: str, seller: str = "") -> tuple:
    """Bank transfer landed — confirm it in the customer's own language."""
    loc = (locale or order.get("locale") or "bg").lower()
    base = base_url(loc)
    n = order.get("order_number", "")
    content = f"""
  <tr><td style="padding:26px 28px 6px;">
    <p style="margin:0 0 8px;font-size:15px;color:#0f172a;">{tr(loc, 'hello', name=order.get('customer_name', ''))}</p>
    <p style="margin:0;font-size:14px;line-height:1.6;color:#334155;">{tr(loc, 'pr_body', n=n)}</p>
  </td></tr>
  <tr><td style="padding:16px 28px 28px;">{_button(f"{base}/checkout/success/{order.get('id', '')}", tr(loc, 'sh_view'))}</td></tr>"""
    return tr(loc, "pr_subject", n=n), _shell(loc, f"{tr(loc, 'order')} {n}", tr(loc, "pr_title"), content, contact_email, seller)

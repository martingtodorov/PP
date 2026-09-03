"""One-off: the six geolocation-help strings were missing in de/cz/hu/pl/sk/si/gr/ro."""
import json

KEYS = ["locateDeniedIos", "locateDeniedSafari", "locateDeniedChrome", "locateDeniedFirefox",
        "locateFramed", "locateOpenTab"]

T = {
 "de": ["Auf dem iPhone: Einstellungen → Datenschutz & Sicherheit → Ortungsdienste → Safari (oder Ihr Browser) → „Bei Verwendung“. Tippen Sie dann in der Adressleiste auf „aA“ → Website-Einstellungen → Standort → Erlauben und versuchen Sie es erneut.",
        "In Safari: Menü Safari → Einstellungen für diese Website → Standort → Erlauben, dann die Seite neu laden.",
        "In Chrome: auf das Symbol links neben der Adresse klicken → Berechtigungen → Standort → Erlauben, dann die Seite neu laden.",
        "In Firefox: auf das Symbol links neben der Adresse klicken → die blockierte Standortberechtigung entfernen, dann neu laden.",
        "Der Browser erlaubt keinen Standortzugriff, wenn die Seite in einem eingebetteten Fenster geöffnet ist.",
        "Öffnen Sie die Seite in einem neuen Tab und versuchen Sie es erneut."],
 "cz": ["Na iPhonu: Nastavení → Soukromí a zabezpečení → Poloha → Safari (nebo váš prohlížeč) → „Při používání“. Poté v adresním řádku klepněte na „aA“ → Nastavení webu → Poloha → Povolit a zkuste to znovu.",
        "V Safari: nabídka Safari → Nastavení pro tento web → Poloha → Povolit, poté stránku obnovte.",
        "V Chrome: klikněte na ikonu vlevo od adresy → Oprávnění → Poloha → Povolit, poté stránku obnovte.",
        "Ve Firefoxu: klikněte na ikonu vlevo od adresy → odeberte zablokované oprávnění k poloze, poté obnovte.",
        "Prohlížeč neumožňuje přístup k poloze, když je web otevřen ve vloženém okně.",
        "Otevřete web na nové kartě a zkuste to znovu."],
 "hu": ["iPhone-on: Beállítások → Adatvédelem és biztonság → Helymeghatározás → Safari (vagy a böngészője) → „Használat közben”. Ezután a címsávban koppintson az „aA” ikonra → Weboldal beállításai → Hely → Engedélyezés, és próbálja újra.",
        "Safariban: Safari menü → Beállítások ehhez a weboldalhoz → Hely → Engedélyezés, majd töltse újra az oldalt.",
        "Chrome-ban: kattintson a cím melletti ikonra → Engedélyek → Hely → Engedélyezés, majd töltse újra az oldalt.",
        "Firefoxban: kattintson a cím melletti ikonra → törölje a letiltott helyengedélyt, majd töltse újra.",
        "A böngésző nem engedi a helyhozzáférést, ha az oldal beágyazott ablakban van megnyitva.",
        "Nyissa meg az oldalt új lapon, és próbálja újra."],
 "pl": ["Na iPhonie: Ustawienia → Prywatność i bezpieczeństwo → Usługi lokalizacji → Safari (lub Twoja przeglądarka) → „Podczas używania”. Następnie w pasku adresu dotknij „aA” → Ustawienia witryny → Lokalizacja → Zezwól i spróbuj ponownie.",
        "W Safari: menu Safari → Ustawienia dla tej witryny → Lokalizacja → Zezwól, następnie odśwież stronę.",
        "W Chrome: kliknij ikonę po lewej stronie adresu → Uprawnienia → Lokalizacja → Zezwól, następnie odśwież stronę.",
        "W Firefoksie: kliknij ikonę po lewej stronie adresu → usuń zablokowane uprawnienie do lokalizacji, następnie odśwież.",
        "Przeglądarka nie pozwala na dostęp do lokalizacji, gdy strona jest otwarta w oknie osadzonym.",
        "Otwórz stronę w nowej karcie i spróbuj ponownie."],
 "sk": ["Na iPhone: Nastavenia → Ochrana osobných údajov a bezpečnosť → Poloha → Safari (alebo váš prehliadač) → „Pri používaní“. Potom v adresnom riadku ťuknite na „aA“ → Nastavenia webu → Poloha → Povoliť a skúste to znova.",
        "V Safari: ponuka Safari → Nastavenia pre tento web → Poloha → Povoliť, potom stránku obnovte.",
        "V Chrome: kliknite na ikonu vľavo od adresy → Povolenia → Poloha → Povoliť, potom stránku obnovte.",
        "Vo Firefoxe: kliknite na ikonu vľavo od adresy → odstráňte zablokované povolenie polohy, potom obnovte.",
        "Prehliadač neumožňuje prístup k polohe, keď je web otvorený vo vloženom okne.",
        "Otvorte web na novej karte a skúste to znova."],
 "si": ["Na iPhonu: Nastavitve → Zasebnost in varnost → Lokacijske storitve → Safari (ali vaš brskalnik) → »Med uporabo«. Nato v naslovni vrstici tapnite »aA« → Nastavitve spletne strani → Lokacija → Dovoli in poskusite znova.",
        "V Safariju: meni Safari → Nastavitve za to spletno stran → Lokacija → Dovoli, nato osvežite stran.",
        "V Chromu: kliknite ikono levo od naslova → Dovoljenja → Lokacija → Dovoli, nato osvežite stran.",
        "V Firefoxu: kliknite ikono levo od naslova → odstranite blokirano dovoljenje za lokacijo, nato osvežite.",
        "Brskalnik ne dovoli dostopa do lokacije, kadar je stran odprta v vdelanem okvirju.",
        "Odprite stran v novem zavihku in poskusite znova."],
 "gr": ["Σε iPhone: Ρυθμίσεις → Απόρρητο και ασφάλεια → Υπηρεσίες τοποθεσίας → Safari (ή το πρόγραμμα περιήγησής σας) → «Κατά τη χρήση». Έπειτα πατήστε «aA» στη γραμμή διευθύνσεων → Ρυθμίσεις ιστότοπου → Τοποθεσία → Να επιτρέπεται και δοκιμάστε ξανά.",
        "Στο Safari: μενού Safari → Ρυθμίσεις για αυτόν τον ιστότοπο → Τοποθεσία → Να επιτρέπεται και ανανεώστε τη σελίδα.",
        "Στο Chrome: πατήστε το εικονίδιο αριστερά από τη διεύθυνση → Άδειες → Τοποθεσία → Να επιτρέπεται και ανανεώστε τη σελίδα.",
        "Στον Firefox: πατήστε το εικονίδιο αριστερά από τη διεύθυνση → αφαιρέστε την αποκλεισμένη άδεια τοποθεσίας και ανανεώστε.",
        "Το πρόγραμμα περιήγησης δεν επιτρέπει πρόσβαση στην τοποθεσία όταν ο ιστότοπος είναι ανοιχτός σε ενσωματωμένο παράθυρο.",
        "Ανοίξτε τον ιστότοπο σε νέα καρτέλα και δοκιμάστε ξανά."],
 "ro": ["Pe iPhone: Setări → Confidențialitate și securitate → Servicii de localizare → Safari (sau browserul dvs.) → „La utilizare”. Apoi atingeți „aA” în bara de adrese → Setări site web → Locație → Permite și încercați din nou.",
        "În Safari: meniul Safari → Setări pentru acest site → Locație → Permite, apoi reîncărcați pagina.",
        "În Chrome: apăsați pictograma din stânga adresei → Permisiuni → Locație → Permite, apoi reîncărcați pagina.",
        "În Firefox: apăsați pictograma din stânga adresei → eliminați permisiunea de locație blocată, apoi reîncărcați.",
        "Browserul nu permite accesul la locație atunci când site-ul este deschis într-o fereastră încorporată.",
        "Deschideți site-ul într-o filă nouă și încercați din nou."],
}

PATH = "/app/frontend/src/i18n/checkoutStrings.js"
src = open(PATH, encoding="utf-8").read()
for loc, vals in T.items():
    head, rest = src.split(f"  {loc}: {{", 1)
    body, tail = rest.split("\n  },", 1)
    block = "".join(f"    {k}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in zip(KEYS, vals))
    src = head + f"  {loc}: {{" + body.rstrip("\n") + "\n" + block.rstrip("\n") + "\n  }," + tail
open(PATH, "w", encoding="utf-8").write(src)
print("filled", len(T), "locales")

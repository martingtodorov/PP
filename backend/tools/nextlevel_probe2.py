"""Probe 2: lockers, weights, validation rules, COD currency rules, services — still via /calculate only."""
import json
import os

import requests

B = "https://api.nextlevel.delivery/v1"
H = {"app-id": os.environ["NL_APP_ID"], "app-secret": os.environ["NL_APP_SECRET"], "accept": "application/json",
     "content-type": "application/json"}
S = {"id": 594, "office_id": 1}
BG = {"country": "BG", "place": "София", "post_code": "1000", "street": "бул. Витоша", "street_no": "1"}
RO = {"country": "RO", "place": "București", "post_code": "010101", "street": "Calea Victoriei", "street_no": "1"}


def get(path, **params):
    r = requests.get(f"{B}{path}", headers=H, params=params, timeout=30)
    return r.status_code, (r.json() if r.text else None)


def calc(body):
    r = requests.post(f"{B}/shipments/calculate", headers=H, data=json.dumps(body, ensure_ascii=False).encode(), timeout=30)
    try:
        j = r.json()
    except ValueError:
        j = r.text[:200]
    if r.status_code == 200 and isinstance(j, dict) and "total" in j:
        return f"OK total={j['total']} base={j.get('base_price')} services={j.get('services_price')}"
    if isinstance(j, dict) and "error" in j:
        return f"ERR {j['error'].get('code')} {str(j['error'].get('message'))[:110]}"
    return f"{r.status_code} {str(j)[:120]}"


def row(label, body):
    print(f"  {label:<58} {calc(body)}")


print("== BG couriers via courier filter (incl. lockers)")
for courier in ("BoxNow", "Econt", "Speedy", "Sameday", "NextLevel"):
    code, offs = get("/offices", country="BG", courier=courier)
    offs = offs if isinstance(offs, list) else []
    machines = [o for o in offs if o.get("is_machine")]
    print(f"  {courier:<10} offices={len(offs)} lockers={len(machines)} sample={json.dumps({k: offs[0].get(k) for k in ('id','office_id','office_code','name','is_machine')}, ensure_ascii=False) if offs else '-'}")
    if machines:
        m = machines[0]
        row(f"  locker {courier} #{m['id']} {m['name'][:22]}", {"sender": S, "receiver": {"office_id": m["id"]}, "weight": 0.5})
        row(f"  locker {courier} + COD 100 EUR", {"sender": S, "receiver": {"office_id": m["id"]}, "weight": 0.5,
                                                 "services": {"cod": {"amount": 100, "currency": "EUR", "processing_type": "BANK"}}})

print("\n== Speedy BG zero-price mystery")
for w in (0.5, 2, 5):
    row(f"Speedy address weight={w}", {"sender": {**S, "courier": "Speedy"}, "receiver": BG, "weight": w})
row("Speedy via receiver.courier? (not in schema)", {"sender": S, "receiver": {**BG, "courier": "Speedy"}, "weight": 0.5})
code, offs = get("/offices", country="BG", courier="Speedy")
if offs:
    row(f"Speedy office #{offs[0]['id']} plain", {"sender": S, "receiver": {"office_id": offs[0]["id"]}, "weight": 0.5})
    row("Speedy office + sender.courier=Speedy", {"sender": {**S, "courier": "Speedy"}, "receiver": {"office_id": offs[0]["id"]}, "weight": 0.5})
    row("Speedy office + sender.courier=Econt (mismatch)", {"sender": {**S, "courier": "Econt"}, "receiver": {"office_id": offs[0]["id"]}, "weight": 0.5})

print("\n== weights (Econt BG address)")
for w in (0.01, 0.1, 0.3, 1, 3, 10, 20, 31, 32, 50):
    row(f"weight={w}", {"sender": S, "receiver": BG, "weight": w})

print("\n== address validation (BG)")
row("Latin city 'Sofia'", {"sender": S, "receiver": {**BG, "place": "Sofia"}, "weight": 0.5})
row("no post_code", {"sender": S, "receiver": {k: v for k, v in BG.items() if k != "post_code"}, "weight": 0.5})
row("wrong post_code 9999", {"sender": S, "receiver": {**BG, "post_code": "9999"}, "weight": 0.5})
row("no street (only place+post_code)", {"sender": S, "receiver": {k: v for k, v in BG.items() if k not in ("street", "street_no")}, "weight": 0.5})
row("free-text 'address' field instead of street", {"sender": S, "receiver": {"country": "BG", "place": "София", "post_code": "1000", "address": "бул. Витоша 1"}, "weight": 0.5})
row("village 'с. Бистрица' no post_code", {"sender": S, "receiver": {"country": "BG", "place": "Бистрица", "street": "Главна", "street_no": "5"}, "weight": 0.5})
row("village 'Бистрица' + post_code 1444", {"sender": S, "receiver": {"country": "BG", "place": "Бистрица", "post_code": "1444", "street": "Главна", "street_no": "5"}, "weight": 0.5})
row("unknown country XX", {"sender": S, "receiver": {**BG, "country": "XX"}, "weight": 0.5})
row("lowercase country 'bg'", {"sender": S, "receiver": {**BG, "country": "bg"}, "weight": 0.5})
row("no weight", {"sender": S, "receiver": BG})
row("weight as string '0.5'", {"sender": S, "receiver": BG, "weight": "0.5"})
row("sender without office_id", {"sender": {"id": 594}, "receiver": BG, "weight": 0.5})
row("wrong sender id 1", {"sender": {"id": 1}, "receiver": BG, "weight": 0.5})

print("\n== COD currency rules")
row("BG cod EUR", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"cod": {"amount": 62.89, "currency": "EUR", "processing_type": "BANK"}}})
row("BG cod BGN (old currency)", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"cod": {"amount": 123, "currency": "BGN", "processing_type": "BANK"}}})
row("BG cod CASH", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"cod": {"amount": 62.89, "currency": "EUR", "processing_type": "CASH"}}})
row("BG cod included_shipping_price", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"cod": {"amount": 62.89, "currency": "EUR", "processing_type": "BANK", "included_shipping_price": True}}})
row("BG cod no processing_type", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"cod": {"amount": 62.89, "currency": "EUR"}}})
row("RO cod RON", {"sender": S, "receiver": RO, "weight": 0.5, "services": {"cod": {"amount": 319, "currency": "RON", "processing_type": "BANK"}}})
row("RO cod EUR (wrong currency)", {"sender": S, "receiver": RO, "weight": 0.5, "services": {"cod": {"amount": 62.89, "currency": "EUR", "processing_type": "BANK"}}})
row("RO cod decimals 319.49", {"sender": S, "receiver": RO, "weight": 0.5, "services": {"cod": {"amount": 319.49, "currency": "RON", "processing_type": "BANK"}}})
row("HU cod HUF 25990", {"sender": S, "receiver": {"country": "HU", "place": "Budapest", "post_code": "1051", "street": "Váci utca", "street_no": "1"}, "weight": 0.5, "services": {"cod": {"amount": 25990, "currency": "HUF", "processing_type": "BANK"}}})
row("PL cod PLN 249", {"sender": S, "receiver": {"country": "PL", "place": "Warszawa", "post_code": "00-001", "street": "Marszałkowska", "street_no": "1"}, "weight": 0.5, "services": {"cod": {"amount": 249, "currency": "PLN", "processing_type": "BANK"}}})
row("CZ cod CZK 1299", {"sender": S, "receiver": {"country": "CZ", "place": "Praha", "post_code": "11000", "street": "Václavské náměstí", "street_no": "1"}, "weight": 0.5, "services": {"cod": {"amount": 1299, "currency": "CZK", "processing_type": "BANK"}}})
row("GR cod EUR", {"sender": S, "receiver": {"country": "GR", "place": "Αθήνα", "post_code": "10431", "street": "Ermou", "street_no": "1"}, "weight": 0.5, "services": {"cod": {"amount": 62.89, "currency": "EUR", "processing_type": "BANK"}}})
row("DE cod EUR", {"sender": S, "receiver": {"country": "DE", "place": "Berlin", "post_code": "10115", "street": "Unter den Linden", "street_no": "1"}, "weight": 0.5, "services": {"cod": {"amount": 62.89, "currency": "EUR", "processing_type": "BANK"}}})
row("cod amount 0", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"cod": {"amount": 0, "currency": "EUR", "processing_type": "BANK"}}})
row("cod amount 5000", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"cod": {"amount": 5000, "currency": "EUR", "processing_type": "BANK"}}})
row("card_cod 62.89", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"card_cod": {"amount": 62.89, "currency": "EUR"}}})

print("\n== other services (BG address)")
row("dv 100 EUR", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"dv": {"amount": 100, "currency": "EUR"}}})
row("fragile", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"fragile": True}})
row("sd saturday", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"sd": True}})
row("obpd OPEN/RECIPIENT", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"obpd": {"option": "OPEN", "return_shipment_payer": "RECIPIENT"}}})
row("signature", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"signature": True}})
row("cod + dv together", {"sender": S, "receiver": BG, "weight": 0.5, "services": {"cod": {"amount": 62.89, "currency": "EUR", "processing_type": "BANK"}, "dv": {"amount": 62.89, "currency": "EUR"}}})

print("\n== RO/GR detail: office by office_code (external) instead of id")
code, offs = get("/offices", country="RO", courier="FAN")
if offs:
    o = offs[0]
    row(f"RO FAN office_id={o['id']}", {"sender": S, "receiver": {"office_id": o["id"]}, "weight": 0.5})
    row(f"RO FAN office_code={o['office_code']} + country", {"sender": S, "receiver": {"country": "RO", "office_code": o["office_code"]}, "weight": 0.5})
    row("RO FAN office_code + courier + country", {"sender": {**S, "courier": "FAN"}, "receiver": {"country": "RO", "office_code": o["office_code"], "place": o["place"], "post_code": o["post_code"]}, "weight": 0.5})
code, offs = get("/offices", country="GR", courier="ACS")
if offs:
    o = offs[0]
    row(f"GR ACS office_id={o['id']} {o['name'][:20]}", {"sender": S, "receiver": {"office_id": o["id"]}, "weight": 0.5})
code, offs = get("/offices", country="GR", courier="BoxNow")
print("  GR BoxNow lockers:", len(offs) if isinstance(offs, list) else offs)
if isinstance(offs, list) and offs:
    row(f"GR BoxNow locker #{offs[0]['id']}", {"sender": S, "receiver": {"office_id": offs[0]["id"]}, "weight": 0.5})

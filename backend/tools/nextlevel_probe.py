"""Probe how NextLevel accepts shipments per country/courier using the non-creating /calculate endpoint."""
import json
import os
import sys
import time

import requests

B = "https://api.nextlevel.delivery/v1"
H = {"app-id": os.environ["NL_APP_ID"], "app-secret": os.environ["NL_APP_SECRET"], "accept": "application/json",
     "content-type": "application/json"}
SENDER = {"id": 594, "office_id": 1}

CITIES = {  # a real receiver address per country
    "BG": {"place": "София", "post_code": "1000", "street": "бул. Витоша", "street_no": "1", "cur": "EUR"},
    "RO": {"place": "București", "post_code": "010101", "street": "Calea Victoriei", "street_no": "1", "cur": "RON"},
    "GR": {"place": "Αθήνα", "post_code": "10431", "street": "Ermou", "street_no": "1", "cur": "EUR"},
    "HU": {"place": "Budapest", "post_code": "1051", "street": "Váci utca", "street_no": "1", "cur": "HUF"},
    "PL": {"place": "Warszawa", "post_code": "00-001", "street": "Marszałkowska", "street_no": "1", "cur": "PLN"},
    "CZ": {"place": "Praha", "post_code": "11000", "street": "Václavské náměstí", "street_no": "1", "cur": "CZK"},
    "SK": {"place": "Bratislava", "post_code": "81101", "street": "Obchodná", "street_no": "1", "cur": "EUR"},
    "SI": {"place": "Ljubljana", "post_code": "1000", "street": "Slovenska cesta", "street_no": "1", "cur": "EUR"},
    "HR": {"place": "Zagreb", "post_code": "10000", "street": "Ilica", "street_no": "1", "cur": "EUR"},
    "DE": {"place": "Berlin", "post_code": "10115", "street": "Unter den Linden", "street_no": "1", "cur": "EUR"},
    "IT": {"place": "Roma", "post_code": "00100", "street": "Via del Corso", "street_no": "1", "cur": "EUR"},
}


def get(path, **params):
    r = requests.get(f"{B}{path}", headers=H, params=params, timeout=30)
    return r.status_code, (r.json() if r.text else None)


def calc(body):
    r = requests.post(f"{B}/shipments/calculate", headers=H, data=json.dumps(body, ensure_ascii=False).encode(), timeout=30)
    try:
        j = r.json()
    except ValueError:
        j = r.text[:200]
    return r.status_code, j


def summarize(code, j):
    if code == 200 and isinstance(j, dict) and "total" in j:
        return f"OK total={j['total']} base={j.get('base_price')} services={j.get('services_price')}"
    if isinstance(j, dict) and "error" in j:
        return f"ERR {j['error'].get('code')} {j['error'].get('message')}"
    return f"{code} {str(j)[:120]}"


def main():
    out = {"countries": {}, "couriers_by_country": {}, "matrix": []}
    code, countries = get("/countries")
    out["countries"] = {c["code"]: c for c in countries}
    print("countries:", ", ".join(f"{c['code']}({c['currency']})" for c in countries))

    # couriers visible through offices, per country
    for cc in CITIES:
        code, offs = get("/offices", country=cc)
        offs = offs if isinstance(offs, list) else []
        by = {}
        for o in offs:
            by.setdefault(o.get("subcontractor"), []).append(o)
        out["couriers_by_country"][cc] = {k: len(v) for k, v in by.items()}
        print(f"\n== {cc}: offices per courier {out['couriers_by_country'][cc]}")
        city = CITIES[cc]
        # 1. address delivery, no courier (NextLevel decides)
        for courier in [None] + sorted(k for k in by if k and k != "NextLevel"):
            recv = {"country": cc, "place": city["place"], "post_code": city["post_code"],
                    "street": city["street"], "street_no": city["street_no"]}
            body = {"sender": {**SENDER, **({"courier": courier} if courier else {})}, "receiver": recv, "weight": 0.5}
            c1, j1 = calc(body)
            cod = {"cod": {"amount": 100, "currency": city["cur"], "processing_type": "BANK", "included_shipping_price": False}}
            c2, j2 = calc({**body, "services": cod})
            row = {"country": cc, "courier": courier or "(auto)", "mode": "address", "plain": summarize(c1, j1), "cod": summarize(c2, j2)}
            out["matrix"].append(row)
            print(f"  address  {row['courier']:<12} plain: {row['plain']:<48} cod: {row['cod']}")
            # 2. office delivery for this courier (first office in that country)
            if courier and by.get(courier):
                o = by[courier][0]
                body_o = {"sender": {**SENDER, "courier": courier}, "receiver": {"office_id": o["id"]}, "weight": 0.5}
                c3, j3 = calc(body_o)
                c4, j4 = calc({**body_o, "services": cod})
                row = {"country": cc, "courier": courier, "mode": f"office#{o['id']} ({o['name'][:30]})",
                       "plain": summarize(c3, j3), "cod": summarize(c4, j4)}
                out["matrix"].append(row)
                print(f"  office   {courier:<12} plain: {row['plain']:<48} cod: {row['cod']}")
            time.sleep(0.15)
    json.dump(out, open("/app/memory/nextlevel_probe.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

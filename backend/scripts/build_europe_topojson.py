"""Build the Europe-only topojson used by the admin traffic map (run once, output is committed).

Source: world-atlas countries-50m (Natural Earth). Only European countries are kept, so the file
stays around 100 KB instead of 740 KB, and every geometry carries its ISO alpha-2 code.
"""
import json
import sys

NUMERIC_TO_ALPHA2 = {
    "008": "AL", "020": "AD", "040": "AT", "056": "BE", "070": "BA", "100": "BG", "112": "BY",
    "191": "HR", "196": "CY", "203": "CZ", "208": "DK", "233": "EE", "246": "FI", "250": "FR",
    "268": "GE", "276": "DE", "292": "GI", "300": "GR", "336": "VA", "348": "HU", "352": "IS",
    "372": "IE", "380": "IT", "428": "LV", "438": "LI", "440": "LT", "442": "LU", "470": "MT",
    "492": "MC", "498": "MD", "499": "ME", "528": "NL", "578": "NO", "616": "PL", "620": "PT",
    "642": "RO", "643": "RU", "674": "SM", "688": "RS", "703": "SK", "705": "SI", "724": "ES",
    "752": "SE", "756": "CH", "792": "TR", "804": "UA", "807": "MK", "826": "GB", "051": "AM",
    "031": "AZ", "398": "KZ", "788": "TN", "504": "MA", "012": "DZ", "434": "LY", "818": "EG",
    "760": "SY", "422": "LB", "376": "IL", "400": "JO", "368": "IQ", "364": "IR",
}


def main(src: str, dst: str):
    topo = json.load(open(src))
    keep = []
    for geom in topo["objects"]["countries"]["geometries"]:
        code = NUMERIC_TO_ALPHA2.get(str(geom.get("id")).zfill(3))
        if not code:
            continue
        geom["properties"] = {"code": code, "name": geom.get("properties", {}).get("name", code)}
        keep.append(geom)

    # only the arcs of the kept countries travel with the file — each arc is delta-encoded on its
    # own, so pruning and re-indexing them is safe and drops ~85% of the size
    used: list = []
    index: dict = {}

    def remap(arcs):
        if isinstance(arcs, list):
            return [remap(a) for a in arcs]
        old = ~arcs if arcs < 0 else arcs
        if old not in index:
            index[old] = len(used)
            used.append(topo["arcs"][old])
        new = index[old]
        return ~new if arcs < 0 else new

    for geom in keep:
        if "arcs" in geom:
            geom["arcs"] = remap(geom["arcs"])

    out = {"type": "Topology", "transform": topo["transform"], "arcs": used,
           "objects": {"countries": {"type": "GeometryCollection", "geometries": keep}}}
    json.dump(out, open(dst, "w"), separators=(",", ":"))
    print(f"{len(keep)} countries, {len(used)} arcs -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

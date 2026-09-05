import { useMemo, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import topo from "../../data/europe-50m.json";

const COUNTRIES = feature(topo, topo.objects.countries).features;
const W = 620;
const H = 460;

/** Europe lit by traffic: the darker the country, the more visitors it sent. */
export const EuropeTrafficMap = ({ rows = [], title = "Трафик по държави" }) => {
  const [hover, setHover] = useState(null);
  const { byCode, max, path } = useMemo(() => {
    const map = {};
    rows.forEach((r) => { if (r.country) map[r.country] = r; });
    const projection = geoMercator().center([15, 55]).scale(470).translate([W / 2, H / 2]);
    return { byCode: map, max: Math.max(1, ...rows.map((r) => r.visitors || 0)), path: geoPath(projection) };
  }, [rows]);

  const shade = (code) => {
    const row = byCode[code];
    if (!row) return "#eef2f7";
    const share = Math.min(1, (row.visitors || 0) / max);
    return `rgba(14, 165, 233, ${0.18 + share * 0.82})`;
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="analytics-map">
      <div className="flex items-baseline justify-between">
        <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
        <p className="text-xs text-slate-500 h-4" data-testid="analytics-map-hover">
          {hover ? `${hover.name}: ${hover.visitors ?? 0}` : ""}
        </p>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto mt-2" role="img"
        aria-label="Карта на посетителите по държави">
        <rect width={W} height={H} fill="#f8fafc" rx="12" />
        {COUNTRIES.map((f) => {
          const code = f.properties.code;
          const row = byCode[code];
          return (
            <path key={code} d={path(f)} fill={shade(code)} stroke="#cbd5e1" strokeWidth={0.6}
              className="transition-[fill] duration-300 cursor-default"
              onMouseEnter={() => setHover({ name: row?.country_name || f.properties.name, visitors: row?.visitors })}
              onMouseLeave={() => setHover(null)}
              data-testid={`map-country-${code}`}>
              <title>{`${row?.country_name || f.properties.name}: ${row?.visitors ?? 0}`}</title>
            </path>
          );
        })}
      </svg>
      <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-400">
        <span>по-малко</span>
        <span className="h-2 flex-1 rounded-full"
          style={{ background: "linear-gradient(90deg, rgba(14,165,233,.18), rgba(14,165,233,1))" }} />
        <span>повече</span>
      </div>
    </div>
  );
};

export default EuropeTrafficMap;

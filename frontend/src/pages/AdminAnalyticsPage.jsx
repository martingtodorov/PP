import { useCallback, useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import AdminLayout from "../components/AdminLayout";
import { api, fmtEUR } from "../lib/api";

const RANGES = [
  { key: "today", label: "Днес" },
  { key: "7d", label: "7 дни" },
  { key: "30d", label: "30 дни" },
  { key: "custom", label: "Период" },
];

const METRICS = [
  { key: "sessions", label: "Сесии", fmt: (v) => String(v) },
  { key: "visitors", label: "Посетители", fmt: (v) => String(v) },
  { key: "views", label: "Показвания", fmt: (v) => String(v) },
  { key: "sales", label: "Продажби", fmt: (v) => fmtEUR(v) },
  { key: "orders", label: "Поръчки", fmt: (v) => String(v) },
  { key: "conversion", label: "Конверсия", fmt: (v) => `${v}%` },
];

const today = () => new Date().toISOString().slice(0, 10);

export default function AdminAnalyticsPage() {
  const [range, setRange] = useState("today");
  const [from, setFrom] = useState(today());
  const [to, setTo] = useState(today());
  const [data, setData] = useState(null);
  const [metric, setMetric] = useState("sessions");

  const load = useCallback(() => {
    const params = { range };
    if (range === "custom") { params.date_from = from; params.date_to = to; }
    api.get("/admin/analytics", { params }).then(({ data }) => setData(data));
  }, [range, from, to]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const cur = data?.current;
  const prev = data?.previous;
  const chart = (cur?.series || []).map((row, i) => ({
    t: data.bucket === "hour" ? `${row.t.slice(11, 13)}:00` : row.t.slice(5),
    current: row[metric] ?? null,
    previous: prev?.series?.[i]?.[metric] ?? null,
  }));
  const active = METRICS.find((m) => m.key === metric);

  return (
    <AdminLayout title="Анализи">
      <div className="flex flex-wrap items-center gap-2 mb-5" data-testid="analytics-ranges">
        {RANGES.map((r) => (
          <button key={r.key} onClick={() => setRange(r.key)}
            className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
              range === r.key ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-slate-400"
            }`}
            data-testid={`analytics-range-${r.key}`}>
            {r.label}
          </button>
        ))}
        {range === "custom" && (
          <span className="flex items-center gap-2 text-sm">
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
              className="border border-slate-300 rounded-md px-2 py-1.5" data-testid="analytics-date-from" />
            <span className="text-slate-400">→</span>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
              className="border border-slate-300 rounded-md px-2 py-1.5" data-testid="analytics-date-to" />
          </span>
        )}
      </div>

      <section className="bg-slate-950 text-white rounded-2xl p-5 sm:p-6" data-testid="analytics-panel">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-4 sm:gap-6">
          <div data-testid="analytics-live">
            <p className="text-sm text-slate-400">Live</p>
            <p className="flex items-center gap-2 text-2xl font-bold">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-70 animate-ping" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400" />
              </span>
              {data?.live ?? 0}
            </p>
            <p className="text-[11px] text-slate-500">последни 5 мин.</p>
          </div>

          {METRICS.map((m) => {
            const delta = data?.deltas?.[m.key];
            return (
              <button key={m.key} onClick={() => setMetric(m.key)}
                className={`text-left rounded-xl px-3 py-2 -mx-3 -my-2 transition-colors ${
                  metric === m.key ? "bg-slate-800" : "hover:bg-slate-900"
                }`}
                data-testid={`analytics-metric-${m.key}`}>
                <p className="text-sm text-slate-400">{m.label}</p>
                <p className="text-2xl font-bold">{cur ? m.fmt(cur[m.key]) : "—"}</p>
                <p className={`text-xs font-semibold ${delta == null ? "text-slate-500" : delta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {delta == null ? "—" : `${delta >= 0 ? "+" : ""}${delta}%`}
                </p>
              </button>
            );
          })}
        </div>

        <div className="h-64 sm:h-72 mt-6" data-testid="analytics-chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="#1e293b" vertical={false} />
              <XAxis dataKey="t" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, color: "#fff", fontSize: 12 }}
                formatter={(v, name) => [active.fmt(v), name === "current" ? "Текущ период" : "Предходен период"]}
              />
              <Line type="monotone" dataKey="previous" stroke="#64748b" strokeWidth={2} strokeDasharray="5 5" dot={false} />
              {/* a small dot per bucket: early in the day „Днес“ has a single point, and a line
                  through one point draws nothing at all */}
              <Line type="monotone" dataKey="current" stroke="#38bdf8" strokeWidth={2.5}
                dot={{ r: 2, fill: "#38bdf8", strokeWidth: 0 }} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <p className="text-[11px] text-slate-500 mt-2">
          Часовете са в местно време ({data?.timezone || "Europe/Sofia"}) — „Днес“ започва в 00:00 и
          показва целите 24 часа, а линията стига до текущия час. Пунктираната линия е същият часови
          отрязък от предходния период.
          {" "}Продажбите не включват цената на доставката.
          {" "}Ботовете (Google, AI индексатори, мониторинг) не се броят
          {data?.bots_excluded ? ` — изключени ${data.bots_excluded} посещения от този период` : ""}.
        </p>
      </section>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6" data-testid="analytics-visitor-windows">
        {[
          { label: "Различни посетители (24 часа)", value: data?.visitors?.["24h"] ?? "—" },
          { label: "Различни посетители (7 дни)", value: data?.visitors?.["7d"] ?? "—" },
          { label: "Различни посетители (30 дни)", value: data?.visitors?.["30d"] ?? "—" },
        ].map((c) => (
          <div key={c.label} className="bg-white border border-slate-200 rounded-xl p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">{c.label}</p>
            <p className="text-xl font-bold text-slate-900 mt-1">{c.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
        {[
          { label: "Продажби (предходен период)", value: prev ? fmtEUR(prev.sales) : "—" },
          { label: "Поръчки (предходен период)", value: prev ? prev.orders : "—" },
          { label: "Сесии (предходен период)", value: prev ? prev.sessions : "—" },
        ].map((c) => (
          <div key={c.label} className="bg-white border border-slate-200 rounded-xl p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">{c.label}</p>
            <p className="text-xl font-bold text-slate-900 mt-1">{c.value}</p>
          </div>
        ))}
      </div>
    </AdminLayout>
  );
}

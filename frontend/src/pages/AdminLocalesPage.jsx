import { useEffect, useState } from "react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { api, formatErr } from "../lib/api";
import { LOCALES, LOCALE_META } from "../i18n/locales";

export default function AdminLocalesPage() {
  const [routes, setRoutes] = useState({});
  const [settings, setSettings] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/admin/settings").then(({ data }) => {
      setSettings(data.settings);
      setRoutes(data.settings.locale_routes || {});
    });
  }, []);

  const set = (loc, field, value) =>
    setRoutes((cur) => ({ ...cur, [loc]: { ...(cur[loc] || {}), [field]: value } }));

  const save = async () => {
    setBusy(true);
    try {
      await api.put("/admin/settings", { value: { ...settings, locale_routes: routes } });
      toast.success("Маршрутите са запазени");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  return (
    <AdminLayout title="Домейни, езици и начални URL адреси">
      <p className="text-sm text-slate-500 mb-6 max-w-3xl">
        Всеки език има свой домейн, URL префикс и начален адрес. Промените се използват за връзките между
        домейните, hreflang таговете и sitemap.xml. Апексът на .eu не се използва — английският живее на /en.
      </p>

      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[880px]">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">Език</th>
              <th className="text-left px-4 py-3">Домейн (origin)</th>
              <th className="text-left px-4 py-3">URL префикс</th>
              <th className="text-left px-4 py-3">Начална страница</th>
              <th className="text-left px-4 py-3">Активен</th>
              <th className="text-left px-4 py-3">Резултат</th>
            </tr>
          </thead>
          <tbody>
            {LOCALES.map((loc) => {
              const r = routes[loc] || {};
              return (
                <tr key={loc} className="border-t border-slate-100" data-testid={`locale-route-${loc}`}>
                  <td className="px-4 py-3 font-medium whitespace-nowrap">{LOCALE_META[loc].label}</td>
                  <td className="px-4 py-3">
                    <input value={r.origin || ""} onChange={(e) => set(loc, "origin", e.target.value)}
                      className="border border-slate-300 rounded-md px-2 py-1.5 text-xs font-mono w-56"
                      data-testid={`route-origin-${loc}`} />
                  </td>
                  <td className="px-4 py-3">
                    <input value={r.prefix ?? ""} onChange={(e) => set(loc, "prefix", e.target.value)}
                      placeholder="/en"
                      className="border border-slate-300 rounded-md px-2 py-1.5 text-xs font-mono w-24"
                      data-testid={`route-prefix-${loc}`} />
                  </td>
                  <td className="px-4 py-3">
                    <input value={r.home_path || "/"} onChange={(e) => set(loc, "home_path", e.target.value)}
                      className="border border-slate-300 rounded-md px-2 py-1.5 text-xs font-mono w-32"
                      data-testid={`route-home-${loc}`} />
                  </td>
                  <td className="px-4 py-3">
                    <input type="checkbox" className="accent-coral-600" checked={r.enabled !== false}
                      onChange={(e) => set(loc, "enabled", e.target.checked)}
                      data-testid={`route-enabled-${loc}`} />
                  </td>
                  <td className="px-4 py-3 text-xs font-mono text-slate-500 break-all">
                    {(r.origin || "") + (r.prefix || "") + (r.home_path === "/" ? "" : r.home_path || "")}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <button onClick={save} disabled={busy}
        className="mt-6 bg-coral-600 hover:bg-coral-700 text-white px-5 py-2 rounded-md text-sm font-semibold disabled:opacity-60"
        data-testid="save-routes-btn">
        {busy ? "Запазване…" : "Запази"}
      </button>
    </AdminLayout>
  );
}

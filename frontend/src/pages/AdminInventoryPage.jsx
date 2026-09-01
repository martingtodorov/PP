import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, PackageX, Boxes } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, fmtEUR, formatErr } from "../lib/api";

const STATE = {
  out: { label: "Изчерпан", cls: "bg-red-100 text-red-700" },
  low: { label: "Малко", cls: "bg-amber-100 text-amber-800" },
  ok: { label: "Наличен", cls: "bg-emerald-50 text-emerald-700" },
};

export default function AdminInventoryPage() {
  const [data, setData] = useState({ items: [], threshold: 5 });
  const [log, setLog] = useState([]);
  const [search, setSearch] = useState("");
  const [edits, setEdits] = useState({});

  const load = useCallback(() => {
    api.get("/admin/inventory").then(({ data }) => setData(data));
    api.get("/admin/inventory/log", { params: { limit: 40 } }).then(({ data }) => setLog(data.log));
  }, []);
  useEffect(() => { load(); }, [load]);

  const key = (i) => `${i.product_id}|${i.variant_name}`;

  const save = async (item) => {
    const value = edits[key(item)];
    if (value === undefined || value === "" || Number(value) === item.stock) return;
    try {
      await api.put("/admin/inventory", {
        product_id: item.product_id,
        variant_name: item.variant_name,
        stock: Number(value),
      });
      toast.success(`${item.title} (${item.variant_name}): ${value} бр.`);
      setEdits((c) => { const n = { ...c }; delete n[key(item)]; return n; });
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  const saveThreshold = async (value) => {
    try {
      await api.put("/admin/inventory/threshold", { threshold: Number(value) });
      toast.success("Прагът е запазен");
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  const q = search.trim().toLowerCase();
  const items = q
    ? data.items.filter((i) => `${i.title} ${i.sku} ${i.variant_name}`.toLowerCase().includes(q))
    : data.items;

  return (
    <AdminLayout title="Наличности">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white border border-slate-200 rounded-xl p-4 flex items-center gap-3" data-testid="inv-out-card">
          <PackageX className="h-5 w-5 text-red-500" />
          <div><p className="text-xs uppercase text-slate-500">Изчерпани</p><p className="text-xl font-bold">{data.out_of_stock ?? 0}</p></div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 flex items-center gap-3" data-testid="inv-low-card">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          <div><p className="text-xs uppercase text-slate-500">Под прага</p><p className="text-xl font-bold">{data.low_stock ?? 0}</p></div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 flex items-center gap-3" data-testid="inv-total-card">
          <Boxes className="h-5 w-5 text-slate-500" />
          <div><p className="text-xs uppercase text-slate-500">Общо бройки</p><p className="text-xl font-bold">{data.total_units ?? 0}</p></div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Търсене по продукт или SKU…"
          className="border border-slate-300 rounded-md px-4 py-2 text-sm flex-1 min-w-[200px] max-w-md"
          data-testid="inventory-search" />
        <label className="text-sm text-slate-600 flex items-center gap-2">
          Праг „малко наличност“
          <input type="number" min="0" defaultValue={data.threshold}
            onBlur={(e) => saveThreshold(e.target.value)}
            className="w-20 border border-slate-300 rounded-md px-2 py-1.5 text-sm"
            data-testid="inventory-threshold" />
        </label>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[760px]">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">Продукт</th>
              <th className="text-left px-4 py-3">Вариант</th>
              <th className="text-left px-4 py-3">SKU</th>
              <th className="text-left px-4 py-3">Цена</th>
              <th className="text-left px-4 py-3">Налични</th>
              <th className="text-left px-4 py-3">Статус</th>
            </tr>
          </thead>
          <tbody data-testid="inventory-table">
            {items.map((i) => {
              const st = STATE[i.state];
              return (
                <tr key={key(i)} className="border-t border-slate-100" data-testid={`inv-row-${i.sku || i.handle + i.variant_name}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {i.image && <img src={i.image} alt="" className="w-9 h-9 object-contain bg-white border border-slate-200 rounded" />}
                      <span className="font-medium">{i.title}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">{i.variant_name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{i.sku || "—"}</td>
                  <td className="px-4 py-3">{fmtEUR(i.price_eur)}</td>
                  <td className="px-4 py-3">
                    <input type="number" min="0"
                      value={edits[key(i)] ?? i.stock}
                      onChange={(e) => setEdits((c) => ({ ...c, [key(i)]: e.target.value }))}
                      onBlur={() => save(i)}
                      onKeyDown={(e) => e.key === "Enter" && save(i)}
                      className="w-20 border border-slate-300 rounded-md px-2 py-1 text-sm"
                      data-testid={`inv-stock-${i.sku || i.variant_name}`} />
                  </td>
                  <td className="px-4 py-3"><span className={`text-xs font-semibold px-2 py-1 rounded ${st.cls}`}>{st.label}</span></td>
                </tr>
              );
            })}
            {items.length === 0 && <tr><td colSpan="6" className="text-center text-slate-500 py-10">Няма резултати.</td></tr>}
          </tbody>
        </table>
      </div>

      <h2 className="font-bold text-slate-900 mt-8 mb-3">Движения по склад</h2>
      <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100" data-testid="inventory-log">
        {log.length === 0 && <p className="p-5 text-sm text-slate-500">Още няма движения.</p>}
        {log.map((l) => (
          <div key={l.id} className="px-4 py-3 flex flex-wrap items-baseline justify-between gap-2 text-sm">
            <span className="text-slate-900">
              {l.product_title} <span className="text-slate-500">({l.variant_name})</span>
            </span>
            <span className="text-slate-500 text-xs">
              {l.reason} · {l.actor} · {new Date(l.created_at).toLocaleString("bg-BG")}
            </span>
            <span className={`font-semibold ${l.change < 0 ? "text-red-600" : "text-emerald-700"}`}>
              {l.change > 0 ? "+" : ""}{l.change} → {l.stock_after}
            </span>
          </div>
        ))}
      </div>
    </AdminLayout>
  );
}

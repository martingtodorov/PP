import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowUp, ArrowDown, Save, EyeOff, TrendingUp } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, fmtEUR, formatErr, img } from "../lib/api";

export default function AdminCollectionsPage() {
  const [collections, setCollections] = useState([]);
  const [handle, setHandle] = useState("2all-the-peptides-1");
  const [items, setItems] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/admin/collections").then(({ data }) => setCollections(data.collections));
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    api.get(`/admin/collections/${handle}/products`)
      .then(({ data }) => { setItems(data.products); setDirty(false); })
      .catch((e) => toast.error(formatErr(e)))
      .finally(() => setLoading(false));
  }, [handle]);
  useEffect(() => { load(); }, [load]);

  const move = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= items.length) return;
    const next = [...items];
    [next[i], next[j]] = [next[j], next[i]];
    setItems(next);
    setDirty(true);
  };

  const moveTo = (i, position) => {
    const next = [...items];
    const [item] = next.splice(i, 1);
    next.splice(Math.max(0, Math.min(position, next.length)), 0, item);
    setItems(next);
    setDirty(true);
  };

  const sortBySales = async () => {
    setBusy(true);
    try {
      await api.post(`/admin/collections/${handle}/order/by-sales`);
      toast.success("Подредено по продажби (най-продаваният е първи)");
      load();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const save = async () => {
    setBusy(true);
    try {
      await api.put(`/admin/collections/${handle}/order`, { handles: items.map((i) => i.handle) });
      toast.success("Подредбата е запазена");
      setDirty(false);
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  return (
    <AdminLayout title="Подредба на колекции">
      <p className="text-sm text-slate-500 mb-5 max-w-3xl">
        Клиентите вече не сортират продуктите — те се показват точно в реда, който зададете тук.
        „Всички пептиди“ определя и реда на „Най-продавани пептиди“ на началната страница.
      </p>

      <div className="flex flex-wrap gap-2 mb-5" data-testid="admin-collection-tabs">
        {collections.map((c) => (
          <button key={c.handle} onClick={() => setHandle(c.handle)}
            className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
              handle === c.handle ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-600 hover:border-slate-400"
            }`}
            data-testid={`admin-collection-${c.handle}`}>
            {c.title}
          </button>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100" data-testid="admin-order-list">
        {loading && <p className="p-5 text-sm text-slate-400">Зареждане…</p>}
        {!loading && items.length === 0 && <p className="p-6 text-sm text-slate-500">Тази колекция няма продукти.</p>}
        {items.map((p, i) => (
          <div key={p.handle} className="flex items-center gap-3 px-3 sm:px-4 py-3" data-testid={`admin-order-row-${p.handle}`}>
            <span className="w-6 text-xs font-bold text-slate-400 tabular-nums">{i + 1}</span>
            {p.image
              ? <img src={img(p.image, 80)} alt="" className="w-10 h-10 object-contain bg-white border border-slate-200 rounded" />
              : <div className="w-10 h-10 bg-slate-100 rounded" />}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-900 truncate">{p.title}</p>
              <p className="text-xs text-slate-500">
                {fmtEUR(p.price_eur)}
                {p.active === false && (
                  <span className="inline-flex items-center gap-1 ml-2 text-slate-400"><EyeOff className="h-3 w-3" /> скрит</span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => moveTo(i, 0)} disabled={i === 0}
                className="hidden sm:block text-[11px] font-semibold text-slate-500 hover:text-slate-900 px-2 disabled:opacity-30"
                data-testid={`admin-order-top-${p.handle}`}>
                Най-горе
              </button>
              <button onClick={() => move(i, -1)} disabled={i === 0}
                className="p-2 text-slate-400 hover:text-slate-900 disabled:opacity-30"
                data-testid={`admin-order-up-${p.handle}`}><ArrowUp className="h-4 w-4" /></button>
              <button onClick={() => move(i, 1)} disabled={i === items.length - 1}
                className="p-2 text-slate-400 hover:text-slate-900 disabled:opacity-30"
                data-testid={`admin-order-down-${p.handle}`}><ArrowDown className="h-4 w-4" /></button>
            </div>
          </div>
        ))}
      </div>

      <div className="sticky bottom-0 mt-5 flex items-center gap-3 bg-slate-50/90 backdrop-blur py-3">
        <button onClick={save} disabled={!dirty || busy}
          className="inline-flex items-center gap-2 bg-coral-600 hover:bg-coral-700 text-white px-5 py-2.5 rounded-md text-sm font-semibold disabled:opacity-50"
          data-testid="admin-order-save-btn">
          <Save className="h-4 w-4" /> {busy ? "Запазване…" : "Запази подредбата"}
        </button>
        <button onClick={sortBySales} disabled={busy}
          className="inline-flex items-center gap-2 border border-slate-300 hover:border-slate-900 px-4 py-2.5 rounded-md text-sm font-semibold disabled:opacity-50"
          data-testid="admin-order-by-sales-btn">
          <TrendingUp className="h-4 w-4" /> Подреди по продажби
        </button>
        {dirty && <span className="text-xs text-amber-700">Има незапазени промени</span>}
      </div>
    </AdminLayout>
  );
}

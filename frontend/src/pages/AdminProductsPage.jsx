import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Pencil, Trash2, Languages, Sparkles, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { api, fmtEUR, formatErr, img } from "../lib/api";
import { LOCALES } from "../i18n/locales";

export default function AdminProductsPage() {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [job, setJob] = useState(null);

  const load = () => api.get("/admin/products").then(({ data }) => setProducts(data.products));
  const loadJob = () => api.get("/admin/translate/bulk").then(({ data }) => setJob(data.job));
  useEffect(() => { load(); loadJob(); }, []);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const t = setInterval(() => {
      api.get("/admin/translate/bulk").then(({ data }) => {
        setJob(data.job);
        if (data.job && data.job.status === "finished") { clearInterval(t); load(); }
      });
    }, 4000);
    return () => clearInterval(t);
  }, [job?.status]);

  const startBulk = async () => {
    if (!window.confirm("Да преведа ли АБСОЛЮТНО ВСИЧКО (продукти, категории, научни статии, страници, текстовете на количката и чекаута, вкл. SEO мета) на всички езици с Claude? Това отнема няколко минути.")) return;
    try {
      const { data } = await api.post("/admin/translate/bulk", { resource: "everything", overwrite: false });
      toast.success(data.message || "Преводът стартира във фонов режим");
      loadJob();
    } catch (e) { toast.error(formatErr(e)); }
  };

  const toggleActive = async (p) => {
    const next = p.active === false;
    setProducts((cur) => cur.map((x) => (x.id === p.id ? { ...x, active: next } : x)));
    try {
      await api.patch(`/admin/products/${p.id}/active`, { active: next });
      toast.success(next ? "Продуктът е активен" : "Продуктът е скрит от магазина");
    } catch (e) {
      toast.error(formatErr(e));
      load();
    }
  };

  const remove = async (p) => {    if (!window.confirm(`Да изтрия ли „${p.title}"?`)) return;
    try {
      await api.delete(`/admin/products/${p.id}`);
      toast.success("Продуктът е изтрит");
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  const filtered = products.filter((p) => p.title.toLowerCase().includes(search.toLowerCase()));
  const busyJob = job && ["queued", "running"].includes(job.status);

  return (
    <AdminLayout title="Продукти">
      <div className="flex flex-wrap gap-3 mb-6 items-center">
        <input
          placeholder="Търсене…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-slate-300 rounded-md px-4 py-2 text-sm flex-1 max-w-md"
          data-testid="products-search"
        />
        <button
          onClick={startBulk}
          disabled={busyJob}
          className="inline-flex items-center gap-2 bg-coral-50 text-coral-700 border border-coral-200 hover:bg-coral-100 px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-60"
          data-testid="bulk-translate-btn"
        >
          <Sparkles className="h-4 w-4" />
          {busyJob ? `Превежда… ${job.done}/${job.total}` : "Преведи всичко с AI (всички езици)"}
        </button>
        <Link
          to="/admin/products/new"
          className="inline-flex items-center gap-2 bg-coral-600 hover:bg-coral-700 text-white px-4 py-2 rounded-md text-sm font-semibold"
          data-testid="new-product-btn"
        >
          <Plus className="h-4 w-4" /> Нов продукт
        </Link>
      </div>

      {job && (
        <div className="mb-6 text-xs text-slate-600 bg-white border border-slate-200 rounded-lg px-4 py-3" data-testid="bulk-translate-status">
          AI превод: <span className="font-semibold">{job.status}</span> · {job.done}/{job.total}
          {job.current ? ` · текущо: ${job.current}` : ""}
          {job.failed?.length ? ` · неуспешни: ${job.failed.length}` : ""}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">Продукт</th>
              <th className="text-left px-4 py-3">Handle</th>
              <th className="text-left px-4 py-3">Варианти</th>
              <th className="text-left px-4 py-3">Цена от</th>
              <th className="text-left px-4 py-3">Наличност</th>
              <th className="text-left px-4 py-3">Активен</th>
              <th className="text-left px-4 py-3">Преводи</th>
              <th className="text-right px-4 py-3">Действия</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => {
              const minPrice = Math.min(...(p.variants || [{ price_eur: 0 }]).map((v) => v.price_eur));
              const stock = (p.variants || []).reduce((s, v) => s + (v.stock || 0), 0);
              const trCount = Object.keys(p.translations || {}).filter((k) => (p.translations[k] || {}).title).length;
              return (
                <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`admin-product-${p.handle}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <img src={img(p.image, 80)} alt="" className="w-10 h-10 object-contain bg-white border border-slate-200 rounded" />
                      <span className="font-medium">
                        {p.title}
                        {(p.variants || []).some((v) => v.sku) && (
                          <span className="block text-[11px] font-mono text-slate-400" data-testid={`admin-product-skus-${p.handle}`}>
                            {(p.variants || []).map((v) => v.sku).filter(Boolean).join(" · ")}
                          </span>
                        )}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {(p.translations?.bg || {}).handle || p.handle}
                    {(p.translations?.bg || {}).handle && (p.translations.bg.handle !== p.handle) && (
                      <span className="block text-[10px] text-slate-400" data-testid={`admin-product-base-handle-${p.handle}`}>
                        ротиран · оригинал: {p.handle}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">{p.variants?.length || 0}</td>
                  <td className="px-4 py-3 font-semibold">{fmtEUR(minPrice)}</td>
                  <td className="px-4 py-3">{stock <= 0 ? <span className="text-red-600 font-medium">Изчерпан</span> : stock}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleActive(p)}
                      className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border transition-colors ${
                        p.active === false
                          ? "bg-slate-100 text-slate-500 border-slate-200 hover:border-slate-400"
                          : "bg-emerald-50 text-emerald-700 border-emerald-200 hover:border-emerald-400"
                      }`}
                      data-testid={`toggle-active-${p.handle}`}>
                      {p.active === false ? <><EyeOff className="h-3.5 w-3.5" /> Скрит</> : <><Eye className="h-3.5 w-3.5" /> Активен</>}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 text-xs text-slate-600">
                      <Languages className="h-3.5 w-3.5" /> {trCount}/{LOCALES.length - 1}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <Link to={`/admin/products/${p.id}`} className="inline-flex items-center gap-1 text-coral-700 hover:underline mr-4" data-testid={`edit-${p.handle}`}>
                      <Pencil className="h-3.5 w-3.5" /> Редакция
                    </Link>
                    <button onClick={() => remove(p)} className="inline-flex items-center gap-1 text-slate-500 hover:text-red-600" data-testid={`delete-${p.handle}`}>
                      <Trash2 className="h-3.5 w-3.5" /> Изтрий
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}

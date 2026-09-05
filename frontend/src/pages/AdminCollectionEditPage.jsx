import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save, Sparkles } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, formatErr } from "../lib/api";
import { LOCALES } from "../i18n/locales";

const FIELDS = [
  ["title", "Заглавие", "input"],
  ["handle", "URL handle", "input"],
  ["description", "Описание", "textarea"],
  ["seo_title", "SEO заглавие", "input"],
  ["seo_description", "SEO описание", "textarea"],
];

export default function AdminCollectionEditPage() {
  const [collections, setCollections] = useState([]);
  const [id, setId] = useState("");
  const [locale, setLocale] = useState("bg");
  const [doc, setDoc] = useState(null);
  const [busy, setBusy] = useState("");

  const load = () =>
    api.get("/admin/collections").then(({ data }) => {
      setCollections(data.collections);
      if (!id && data.collections.length) setId(data.collections[0].id);
    });
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);
  useEffect(() => { setDoc(collections.find((c) => c.id === id) || null); }, [id, collections]);

  if (!doc) return <AdminLayout title="Колекции"><p className="text-sm text-slate-400">Зареждане…</p></AdminLayout>;

  const tr = (doc.translations || {})[locale] || {};
  const value = (f) => (locale === "bg" ? doc[f] ?? "" : tr[f] ?? "");
  const setValue = (f, v) => {
    if (locale === "bg") setDoc({ ...doc, [f]: v });
    else setDoc({ ...doc, translations: { ...(doc.translations || {}), [locale]: { ...tr, [f]: v } } });
  };

  const save = async () => {
    setBusy("save");
    try {
      await api.put(`/admin/collections/${doc.id}`, {
        handle: doc.handle,
        title: doc.title || "",
        description: doc.description || "",
        image: doc.image || "",
        sort_order: Number(doc.sort_order) || 0,
        nav_hidden: !!doc.nav_hidden,
        delisted: !!doc.delisted,
        seo_title: doc.seo_title || "",
        seo_description: doc.seo_description || "",
        translations: doc.translations || {},
      });
      toast.success("Колекцията е запазена");
      load();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };

  const translate = async (locales) => {
    setBusy("tr");
    try {
      const { data } = await api.post("/admin/translate", {
        resource: "collection", id: doc.id, locales, overwrite: true,
      });
      setDoc(data.resource);
      toast.success(`Преведено: ${(data.translated || []).join(", ") || "нищо ново"}`);
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };

  return (
    <AdminLayout title="Колекции — съдържание и SEO">
      <div className="flex flex-wrap gap-3 items-center mb-6">
        <select value={id} onChange={(e) => setId(e.target.value)}
          className="border border-slate-300 rounded-md px-3 py-2 text-sm" data-testid="collection-select">
          {collections.map((c) => <option key={c.id} value={c.id}>{`${c.title} · /${c.handle}`}</option>)}
        </select>
        <button onClick={() => translate(LOCALES.filter((l) => l !== "bg"))} disabled={!!busy}
          className="inline-flex items-center gap-2 bg-coral-50 text-coral-700 border border-coral-200 hover:bg-coral-100 px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-60"
          data-testid="collection-translate-all-btn">
          <Sparkles className="h-4 w-4" /> {busy === "tr" ? "Превежда…" : "Преведи на всички езици"}
        </button>
        <button onClick={save} disabled={!!busy}
          className="inline-flex items-center gap-2 bg-coral-600 hover:bg-coral-700 text-white px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-60"
          data-testid="collection-save-btn">
          <Save className="h-4 w-4" /> Запази
        </button>
      </div>

      <div className="flex flex-wrap gap-2 mb-5" data-testid="collection-locale-tabs">
        {LOCALES.map((l) => (
          <button key={l} onClick={() => setLocale(l)}
            className={`px-3 py-1.5 rounded-full text-xs font-bold border ${
              locale === l ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200"}`}
            data-testid={`collection-locale-${l}`}>
            {l.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 max-w-3xl">
        {FIELDS.map(([f, label, kind]) => (
          <label key={f} className="block">
            <span className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</span>
            {kind === "textarea" ? (
              <textarea rows={f === "description" ? 6 : 2} value={value(f)} onChange={(e) => setValue(f, e.target.value)}
                className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                data-testid={`collection-${f}`} />
            ) : (
              <input value={value(f)} onChange={(e) => setValue(f, e.target.value)}
                className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                data-testid={`collection-${f}`} />
            )}
          </label>
        ))}

        {locale === "bg" && (
          <div className="flex flex-wrap gap-5 items-center pt-2 border-t border-slate-100">
            <label className="text-sm text-slate-700 flex items-center gap-2">
              Подредба
              <input type="number" value={doc.sort_order ?? 0}
                onChange={(e) => setDoc({ ...doc, sort_order: e.target.value })}
                className="w-20 border border-slate-300 rounded-md px-2 py-1 text-sm" data-testid="collection-sort-order" />
            </label>
            <label className="text-sm text-slate-700 flex items-center gap-2">
              <input type="checkbox" checked={!!doc.nav_hidden}
                onChange={(e) => setDoc({ ...doc, nav_hidden: e.target.checked })}
                data-testid="collection-nav-hidden" />
              Скрий от менюто и плочките (страницата остава активна)
            </label>
            <label className="text-sm text-slate-700 flex items-center gap-2">
              <input type="checkbox" checked={!!doc.delisted}
                onChange={(e) => setDoc({ ...doc, delisted: e.target.checked })}
                data-testid="collection-delisted" />
              <span>
                Изтегли от сайта
                <span className="block text-[11px] text-slate-400">
                  URL-ът връща 404, изчезва от менюто, каталога и sitemap-а
                </span>
              </span>
            </label>
          </div>
        )}

        {locale !== "bg" && (
          <button onClick={() => translate([locale])} disabled={!!busy}
            className="text-xs font-semibold text-coral-700 hover:underline" data-testid={`collection-translate-${locale}`}>
            Преведи само {locale.toUpperCase()} с AI
          </button>
        )}
      </div>
    </AdminLayout>
  );
}

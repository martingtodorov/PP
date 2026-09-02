import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Upload, X, Plus, Trash2, Sparkles, ArrowLeft, GripVertical } from "lucide-react";
import { toast } from "sonner";
import AdminLayout from "../components/AdminLayout";
import { api, BACKEND_URL, formatErr, img } from "../lib/api";
import { LOCALES, LOCALE_META } from "../i18n/locales";
import { isAllCollection } from "../lib/collections";

const EMPTY = {
  handle: "", title: "", subtitle: "", description: "", image: "", images: [],
  variants: [{ name: "", price_eur: 0, stock: 0, sku: "" }],
  collections: [], tags: [], featured: false,
  specs: { cas: "", formula: "", mw: "", purity: "" },
  seo_title: "", seo_description: "", translations: {},
};

const absUrl = (u) => (u && u.startsWith("/api/") ? `${BACKEND_URL}${u}` : u);

export default function AdminProductEditPage() {
  const { id } = useParams();
  const isNew = !id;
  const nav = useNavigate();
  const [p, setP] = useState(EMPTY);
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [tab, setTab] = useState("bg");
  const fileRef = useRef(null);

  useEffect(() => {
    api.get("/admin/collections").then(({ data }) => setCollections(data.collections));
    if (!isNew) {
      api.get(`/admin/products/${id}`)
        .then(({ data }) => setP({ ...EMPTY, ...data.product, specs: { ...EMPTY.specs, ...(data.product.specs || {}) } }))
        .catch((e) => toast.error(formatErr(e)))
        .finally(() => setLoading(false));
    }
  }, [id, isNew]);

  const set = (patch) => setP((cur) => ({ ...cur, ...patch }));
  const setTr = (loc, field, value) =>
    setP((cur) => ({
      ...cur,
      translations: { ...cur.translations, [loc]: { ...(cur.translations[loc] || {}), [field]: value } },
    }));

  const uploadFiles = async (files) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      const urls = [];
      for (const f of files) {
        const fd = new FormData();
        fd.append("file", f);
        const { data } = await api.post("/admin/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
        urls.push(absUrl(data.url));
      }
      setP((cur) => {
        const images = [...(cur.images || []), ...urls];
        return { ...cur, images, image: cur.image || images[0] };
      });
      toast.success(`${urls.length} снимки качени`);
    } catch (e) {
      toast.error(formatErr(e));
    } finally {
      setUploading(false);
    }
  };

  const removeImage = (idx) =>
    setP((cur) => {
      const images = cur.images.filter((_, i) => i !== idx);
      return { ...cur, images, image: images.includes(cur.image) ? cur.image : images[0] || "" };
    });

  const moveImage = (idx, dir) =>
    setP((cur) => {
      const images = [...cur.images];
      const target = idx + dir;
      if (target < 0 || target >= images.length) return cur;
      [images[idx], images[target]] = [images[target], images[idx]];
      return { ...cur, images, image: images[0] };
    });

  const addImageUrl = () => {
    const url = window.prompt("URL на снимка:");
    if (!url) return;
    setP((cur) => ({ ...cur, images: [...(cur.images || []), url], image: cur.image || url }));
  };

  const save = async () => {
    if (!p.handle || !p.title) { toast.error("Handle и заглавие са задължителни"); return; }
    setSaving(true);
    const payload = {
      ...p,
      image: p.image || p.images?.[0] || "",
      variants: p.variants.map((v) => ({ ...v, price_eur: Number(v.price_eur) || 0, stock: Number(v.stock) || 0 })),
    };
    delete payload.id;
    delete payload.created_at;
    delete payload.base_handle;
    delete payload.handles;
    try {
      if (isNew) {
        const { data } = await api.post("/admin/products", payload);
        toast.success("Продуктът е създаден");
        nav(`/admin/products/${data.product.id}`);
      } else {
        await api.put(`/admin/products/${id}`, payload);
        toast.success("Промените са запазени");
      }
    } catch (e) {
      toast.error(formatErr(e));
    } finally {
      setSaving(false);
    }
  };

  const translate = async (locales) => {
    if (isNew) { toast.error("Запазете продукта преди превод"); return; }
    setTranslating(true);
    try {
      const { data } = await api.post("/admin/translate", { resource: "product", id, locales, overwrite: true });
      if (data.resource) setP((cur) => ({ ...cur, translations: data.resource.translations || {} }));
      toast.success(`Преведено: ${(data.translated || []).join(", ") || "нищо ново"}`);
    } catch (e) {
      toast.error(formatErr(e));
    } finally {
      setTranslating(false);
    }
  };

  if (loading) return <AdminLayout title="Продукт"><p className="text-slate-500">Зареждане…</p></AdminLayout>;

  const trLocales = LOCALES.filter((l) => l !== "bg");

  return (
    <AdminLayout title={isNew ? "Нов продукт" : p.title}>
      <div className="flex items-center justify-between mb-6">
        <Link to="/admin/products" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-coral-600">
          <ArrowLeft className="h-4 w-4" /> Всички продукти
        </Link>
        <button onClick={save} disabled={saving}
          className="bg-coral-600 hover:bg-coral-700 text-white px-5 py-2 rounded-md text-sm font-semibold disabled:opacity-60"
          data-testid="save-product-btn">
          {saving ? "Запазване…" : "Запази"}
        </button>
      </div>

      {/* Locale tabs */}
      <div className="flex flex-wrap gap-1.5 mb-6" data-testid="locale-tabs">
        {LOCALES.map((l) => (
          <button key={l} onClick={() => setTab(l)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
              tab === l ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
            }`}
            data-testid={`locale-tab-${l}`}>
            {l.toUpperCase()}
            {l !== "bg" && (p.translations?.[l] || {}).title && <span className="ml-1 text-coral-500">•</span>}
          </button>
        ))}
        <button onClick={() => translate(trLocales)} disabled={translating}
          className="ml-auto inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold bg-coral-50 text-coral-700 border border-coral-200 hover:bg-coral-100 disabled:opacity-60"
          data-testid="translate-all-btn">
          <Sparkles className="h-3.5 w-3.5" /> {translating ? "Превежда…" : "Преведи всички езици с AI"}
        </button>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Content */}
          <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
            <h2 className="font-bold text-slate-900">
              Съдържание · {LOCALE_META[tab].label}
            </h2>
            {tab === "bg" ? (
              <>
                <Field label="Заглавие" value={p.title} onChange={(v) => set({ title: v })} testId="field-title" />
                <Field label="Handle (URL)" value={p.handle} onChange={(v) => set({ handle: v })} mono testId="field-handle" />
                <Field label="Подзаглавие" value={p.subtitle} onChange={(v) => set({ subtitle: v })} testId="field-subtitle" />
                <TextArea label="Описание (HTML)" value={p.description} onChange={(v) => set({ description: v })} testId="field-description" />
              </>
            ) : (
              <>
                <div className="flex justify-end">
                  <button onClick={() => translate([tab])} disabled={translating}
                    className="inline-flex items-center gap-2 text-xs font-semibold text-coral-700 hover:underline"
                    data-testid={`translate-${tab}-btn`}>
                    <Sparkles className="h-3.5 w-3.5" /> Преведи този език
                  </button>
                </div>
                <Field label="Заглавие" value={(p.translations[tab] || {}).title || ""} onChange={(v) => setTr(tab, "title", v)} testId={`tr-title-${tab}`} />
                <Field label={`Handle за ${LOCALE_META[tab].label} (различен URL за този домейн)`} mono
                  value={(p.translations[tab] || {}).handle || ""} onChange={(v) => setTr(tab, "handle", v)} testId={`tr-handle-${tab}`} />
                <TextArea label="Описание (HTML)" value={(p.translations[tab] || {}).description || ""} onChange={(v) => setTr(tab, "description", v)} testId={`tr-desc-${tab}`} />
                <p className="text-xs text-slate-500">
                  Промяната на handle тук важи само за {LOCALE_META[tab].label} ({LOCALE_META[tab].origin}
                  {LOCALE_META[tab].prefix}). Останалите домейни не се променят.
                </p>
              </>
            )}
          </section>

          {/* Images */}
          <section className="bg-white border border-slate-200 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-slate-900">Снимки</h2>
              <div className="flex gap-2">
                <button onClick={addImageUrl} className="text-xs text-slate-600 hover:text-coral-600" data-testid="add-image-url-btn">+ URL</button>
                <button onClick={() => fileRef.current?.click()} disabled={uploading}
                  className="inline-flex items-center gap-2 bg-slate-900 text-white px-3 py-1.5 rounded-md text-xs font-semibold disabled:opacity-60"
                  data-testid="upload-image-btn">
                  <Upload className="h-3.5 w-3.5" /> {uploading ? "Качване…" : "Качи снимки"}
                </button>
              </div>
            </div>
            <input ref={fileRef} type="file" accept="image/*" multiple className="hidden"
              onChange={(e) => uploadFiles(Array.from(e.target.files || []))} data-testid="image-file-input" />
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); uploadFiles(Array.from(e.dataTransfer.files || [])); }}
              className="border-2 border-dashed border-slate-200 rounded-lg p-4"
              data-testid="image-dropzone"
            >
              {(p.images || []).length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-6">Пуснете снимки тук или използвайте бутона по-горе</p>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
                  {p.images.map((src, i) => (
                    <div key={`${src}-${i}`} className="relative group border border-slate-200 rounded-lg bg-white p-1" data-testid={`product-image-${i}`}>
                      <img src={img(src, 400)} alt="" className="w-full aspect-square object-contain" />
                      {i === 0 && <span className="absolute top-1 left-1 bg-coral-600 text-white text-[10px] px-1.5 py-0.5 rounded">основна</span>}
                      <div className="absolute inset-x-1 bottom-1 flex justify-between opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => moveImage(i, -1)} className="bg-white/90 border border-slate-200 rounded px-1 text-xs">←</button>
                        <button onClick={() => moveImage(i, 1)} className="bg-white/90 border border-slate-200 rounded px-1 text-xs">→</button>
                      </div>
                      <button onClick={() => removeImage(i)}
                        className="absolute -top-2 -right-2 bg-white border border-slate-300 rounded-full p-1 shadow-sm"
                        data-testid={`remove-image-${i}`}>
                        <X className="h-3 w-3 text-slate-600" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Variants */}
          <section className="bg-white border border-slate-200 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-slate-900">Варианти</h2>
              <button
                onClick={() => set({ variants: [...p.variants, { name: "", price_eur: 0, stock: 0, sku: "" }] })}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-coral-700"
                data-testid="add-variant-btn"
              >
                <Plus className="h-3.5 w-3.5" /> Добави вариант
              </button>
            </div>
            <div className="space-y-3">
              {p.variants.map((v, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-center" data-testid={`variant-row-${i}`}>
                  <GripVertical className="h-4 w-4 text-slate-300 col-span-1" />
                  <input placeholder="Име (5mg)" value={v.name}
                    onChange={(e) => { const vs = [...p.variants]; vs[i] = { ...v, name: e.target.value }; set({ variants: vs }); }}
                    className="col-span-3 border border-slate-300 rounded-md px-2 py-1.5 text-sm" data-testid={`variant-name-${i}`} />
                  <input placeholder="SKU" value={v.sku}
                    onChange={(e) => { const vs = [...p.variants]; vs[i] = { ...v, sku: e.target.value }; set({ variants: vs }); }}
                    className="col-span-3 border border-slate-300 rounded-md px-2 py-1.5 text-sm font-mono" data-testid={`variant-sku-${i}`} />
                  <input placeholder="EUR" type="number" step="0.01" value={v.price_eur}
                    onChange={(e) => { const vs = [...p.variants]; vs[i] = { ...v, price_eur: e.target.value }; set({ variants: vs }); }}
                    className="col-span-2 border border-slate-300 rounded-md px-2 py-1.5 text-sm" data-testid={`variant-price-${i}`} />
                  <input placeholder="Бр." type="number" value={v.stock}
                    onChange={(e) => { const vs = [...p.variants]; vs[i] = { ...v, stock: e.target.value }; set({ variants: vs }); }}
                    className="col-span-2 border border-slate-300 rounded-md px-2 py-1.5 text-sm" data-testid={`variant-stock-${i}`} />
                  <button onClick={() => set({ variants: p.variants.filter((_, x) => x !== i) })}
                    className="col-span-1 text-slate-400 hover:text-red-600" data-testid={`remove-variant-${i}`}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-3">
            <h2 className="font-bold text-slate-900">Категории</h2>
            {collections.filter((c) => !isAllCollection(c)).map((c) => (
              <label key={c.handle} className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" className="accent-coral-600"
                  checked={p.collections?.includes(c.handle)}
                  onChange={(e) => set({
                    collections: e.target.checked
                      ? [...(p.collections || []), c.handle]
                      : p.collections.filter((h) => h !== c.handle),
                  })}
                  data-testid={`collection-${c.handle}`} />
                {c.title}
              </label>
            ))}
            <label className="flex items-center gap-2 text-sm text-slate-700 border-t border-slate-100 pt-3">
              <input type="checkbox" className="accent-coral-600" checked={!!p.featured}
                onChange={(e) => set({ featured: e.target.checked })} data-testid="field-featured" />
              Показвай като препоръчан
            </label>
          </section>

          <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-3">
            <h2 className="font-bold text-slate-900">Спецификация</h2>
            {["cas", "formula", "mw", "purity"].map((k) => (
              <Field key={k} label={k.toUpperCase()} value={p.specs?.[k] || ""}
                onChange={(v) => set({ specs: { ...p.specs, [k]: v } })} testId={`spec-${k}`} />
            ))}
          </section>

          <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-3">
            <h2 className="font-bold text-slate-900">SEO</h2>
            <Field label="SEO заглавие" value={p.seo_title} onChange={(v) => set({ seo_title: v })} testId="field-seo-title" />
            <TextArea label="SEO описание" rows={3} value={p.seo_description} onChange={(v) => set({ seo_description: v })} testId="field-seo-desc" />
          </section>
        </div>
      </div>
    </AdminLayout>
  );
}

const Field = ({ label, value, onChange, mono, testId }) => (
  <label className="block">
    <span className="block text-xs font-medium text-slate-500 mb-1">{label}</span>
    <input
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-coral-600 ${mono ? "font-mono" : ""}`}
      data-testid={testId}
    />
  </label>
);

const TextArea = ({ label, value, onChange, rows = 10, testId }) => (
  <label className="block">
    <span className="block text-xs font-medium text-slate-500 mb-1">{label}</span>
    <textarea
      value={value || ""}
      rows={rows}
      onChange={(e) => onChange(e.target.value)}
      className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm font-mono leading-relaxed focus:outline-none focus:border-coral-600"
      data-testid={testId}
    />
  </label>
);

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, ArrowUp, ArrowDown, Sparkles, Save } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, formatErr } from "../lib/api";
import { LOCALE_META } from "../i18n/locales";

const empty = { title: "", html: "", faq_items: [] };

export default function AdminPagesPage() {
  const [meta, setMeta] = useState({ slugs: [], locales: [] });
  const [slug, setSlug] = useState("какво-са-пептиди");
  const [locale, setLocale] = useState("bg");
  const [page, setPage] = useState(empty);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [translating, setTranslating] = useState(false);

  const loadMeta = useCallback(() => {
    api.get("/admin/pages").then(({ data }) => setMeta(data));
  }, []);

  useEffect(() => { loadMeta(); }, [loadMeta]);

  useEffect(() => {
    setLoading(true);
    api.get(`/admin/pages/${slug}/${locale}`)
      .then(({ data }) => setPage({ ...empty, ...data.page }))
      .catch((e) => toast.error(formatErr(e)))
      .finally(() => setLoading(false));
  }, [slug, locale]);

  const save = async () => {
    setBusy(true);
    try {
      await api.put(`/admin/pages/${slug}/${locale}`, {
        title: page.title || "",
        html: page.html || "",
        faq_items: page.faq_items || [],
      });
      toast.success(`Запазено: ${LOCALE_META[locale].label}`);
      loadMeta();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const translate = async (overwrite) => {
    setTranslating(true);
    try {
      const { data } = await api.post(`/admin/pages/${slug}/translate`, { locales: [], overwrite });
      if (!data.translated.length) toast.info(data.message || "Няма нови езици за превод");
      else toast.success(`Преведено на: ${data.translated.join(", ")}`);
      if (data.failed?.length) toast.error(`Неуспешни: ${data.failed.join(", ")}`);
      loadMeta();
      if (locale !== "bg") {
        const { data: fresh } = await api.get(`/admin/pages/${slug}/${locale}`);
        setPage({ ...empty, ...fresh.page });
      }
    } catch (e) { toast.error(formatErr(e)); } finally { setTranslating(false); }
  };

  const items = page.faq_items || [];
  const setItems = (next) => setPage((p) => ({ ...p, faq_items: next }));
  const setItem = (i, field, value) => setItems(items.map((it, idx) => (idx === i ? { ...it, [field]: value } : it)));
  const move = (i, dir) => {
    const next = [...items];
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    setItems(next);
  };

  const isFaq = slug === "faq";
  const current = meta.slugs.find((s) => s.slug === slug);

  return (
    <AdminLayout title="Страници по език">
      <p className="text-sm text-slate-500 mb-6 max-w-3xl">
        Редактирайте съдържанието на статичните страници за всеки език. Съдържанието се въвежда като HTML.
        Ако липсва превод, витрината използва английската, а после българската версия.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">
        <aside className="bg-white border border-slate-200 rounded-xl p-2 h-fit" data-testid="admin-pages-slug-list">
          {meta.slugs.map((s) => (
            <button key={s.slug} onClick={() => setSlug(s.slug)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                slug === s.slug ? "bg-coral-50 text-coral-700 font-semibold" : "text-slate-600 hover:bg-slate-50"
              }`}
              data-testid={`admin-page-slug-${s.slug}`}>
              {s.label}
              <span className="block text-[11px] text-slate-400 font-normal">
                {Object.values(s.filled || {}).filter(Boolean).length} / {meta.locales.length} езика
              </span>
            </button>
          ))}
        </aside>

        <section>
          <div className="flex flex-wrap gap-1.5 mb-4" data-testid="admin-pages-locale-tabs">
            {meta.locales.map((loc) => {
              const filled = current?.filled?.[loc];
              return (
                <button key={loc} onClick={() => setLocale(loc)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                    locale === loc
                      ? "bg-slate-900 text-white border-slate-900"
                      : filled
                        ? "bg-white text-slate-700 border-slate-300 hover:border-slate-900"
                        : "bg-white text-slate-400 border-dashed border-slate-300 hover:border-slate-500"
                  }`}
                  data-testid={`admin-page-locale-${loc}`}>
                  {LOCALE_META[loc]?.label || loc}
                </button>
              );
            })}
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5">
            {loading ? (
              <p className="text-sm text-slate-400">Зареждане…</p>
            ) : (
              <>
                <label className="block text-xs uppercase tracking-wide text-slate-500 font-bold mb-1">Заглавие</label>
                <input value={page.title || ""} onChange={(e) => setPage((p) => ({ ...p, title: e.target.value }))}
                  className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-5"
                  data-testid="admin-page-title-input" />

                <label className="block text-xs uppercase tracking-wide text-slate-500 font-bold mb-1">
                  Съдържание (HTML)
                </label>
                <textarea value={page.html || ""} onChange={(e) => setPage((p) => ({ ...p, html: e.target.value }))}
                  rows={isFaq ? 4 : 16}
                  className="w-full border border-slate-300 rounded-md px-3 py-2 text-xs font-mono leading-relaxed"
                  placeholder="<p>Текст…</p>"
                  data-testid="admin-page-html-input" />
                <p className="text-[11px] text-slate-400 mt-1">
                  Разрешени тагове: p, h2, h3, ul, ol, li, strong, em, a, br.
                </p>

                {isFaq && (
                  <div className="mt-6" data-testid="admin-page-faq-editor">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs uppercase tracking-wide text-slate-500 font-bold">Въпроси и отговори</span>
                      <button onClick={() => setItems([...items, { q: "", a: "" }])}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-coral-700 hover:text-coral-800"
                        data-testid="admin-faq-add-btn">
                        <Plus className="h-3.5 w-3.5" /> Добави въпрос
                      </button>
                    </div>
                    <div className="space-y-3">
                      {items.map((it, i) => (
                        <div key={i} className="border border-slate-200 rounded-lg p-3" data-testid={`admin-faq-item-${i}`}>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-[11px] font-bold text-slate-400">#{i + 1}</span>
                            <div className="ml-auto flex items-center gap-1">
                              <button onClick={() => move(i, -1)} className="p-1 text-slate-400 hover:text-slate-700"
                                data-testid={`admin-faq-up-${i}`}><ArrowUp className="h-3.5 w-3.5" /></button>
                              <button onClick={() => move(i, 1)} className="p-1 text-slate-400 hover:text-slate-700"
                                data-testid={`admin-faq-down-${i}`}><ArrowDown className="h-3.5 w-3.5" /></button>
                              <button onClick={() => setItems(items.filter((_, idx) => idx !== i))}
                                className="p-1 text-slate-400 hover:text-red-600"
                                data-testid={`admin-faq-delete-${i}`}><Trash2 className="h-3.5 w-3.5" /></button>
                            </div>
                          </div>
                          <input value={it.q || ""} onChange={(e) => setItem(i, "q", e.target.value)}
                            placeholder="Въпрос"
                            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-2"
                            data-testid={`admin-faq-q-${i}`} />
                          <textarea value={it.a || ""} onChange={(e) => setItem(i, "a", e.target.value)}
                            placeholder="Отговор" rows={3}
                            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
                            data-testid={`admin-faq-a-${i}`} />
                        </div>
                      ))}
                      {!items.length && <p className="text-sm text-slate-400">Няма въпроси. Добавете първия.</p>}
                    </div>
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-3 mt-6 pt-5 border-t border-slate-100">
                  <button onClick={save} disabled={busy}
                    className="inline-flex items-center gap-2 bg-coral-600 hover:bg-coral-700 text-white px-5 py-2 rounded-md text-sm font-semibold disabled:opacity-60"
                    data-testid="admin-page-save-btn">
                    <Save className="h-4 w-4" /> {busy ? "Запазване…" : "Запази"}
                  </button>
                  <button onClick={() => translate(false)} disabled={translating}
                    className="inline-flex items-center gap-2 border border-slate-300 hover:border-slate-900 px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-60"
                    data-testid="admin-page-translate-btn">
                    <Sparkles className="h-4 w-4" /> {translating ? "Превеждане…" : "Преведи с AI (само липсващите)"}
                  </button>
                  <button onClick={() => translate(true)} disabled={translating}
                    className="text-xs font-semibold text-slate-500 hover:text-slate-900 underline"
                    data-testid="admin-page-retranslate-btn">
                    Презапиши всички езици от българския
                  </button>
                </div>
                {page.updated_at && (
                  <p className="text-[11px] text-slate-400 mt-3">Последна промяна: {new Date(page.updated_at).toLocaleString("bg-BG")}</p>
                )}
              </>
            )}
          </div>
        </section>
      </div>
    </AdminLayout>
  );
}

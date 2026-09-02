import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Upload, Link2, Save, ExternalLink } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { api, BACKEND_URL, formatErr, img } from "../lib/api";

const absUrl = (u) => (u && u.startsWith("/api/") ? `${BACKEND_URL}${u}` : u);

const ArticleRow = ({ article, onSaved }) => {
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState("");
  const value = (key) => (key in draft ? draft[key] : (article[key] ?? ""));
  const dirty = Object.keys(draft).length > 0;

  const run = async (kind, fn) => {
    setBusy(kind);
    try { await fn(); } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };

  const save = (patch) => run("save", async () => {
    const body = { ...draft, ...patch };
    const { data } = await api.patch(`/admin/articles/${article.handle}`, body);
    setDraft({});
    onSaved(data.article);
    toast.success("Статията е запазена");
  });

  const uploadCover = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      await run("upload", async () => {
        const fd = new FormData();
        fd.append("file", file);
        const { data } = await api.post("/admin/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
        await save({ image: absUrl(data.url) });
      });
    };
    input.click();
  };

  const pasteUrl = () => {
    const url = window.prompt("URL на снимката:", value("image"));
    if (url) save({ image: url });
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-col sm:flex-row gap-4"
      data-testid={`article-row-${article.handle}`}>
      <div className="sm:w-48 shrink-0">
        <div className="aspect-[4/3] rounded-lg border border-slate-200 bg-slate-50 overflow-hidden flex items-center justify-center">
          {value("image") ? (
            <img src={img(value("image"), 400)} alt={article.title}
              className="w-full h-full object-cover" data-testid={`article-cover-${article.handle}`} />
          ) : (
            <span className="text-xs text-slate-400">без снимка</span>
          )}
        </div>
        <div className="flex gap-2 mt-2">
          <button type="button" onClick={uploadCover} disabled={Boolean(busy)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-coral-700 hover:text-coral-800 disabled:opacity-50"
            data-testid={`article-upload-${article.handle}`}>
            {busy === "upload" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
            Качи снимка
          </button>
          <button type="button" onClick={pasteUrl} disabled={Boolean(busy)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 disabled:opacity-50"
            data-testid={`article-url-${article.handle}`}>
            <Link2 className="h-3.5 w-3.5" /> URL
          </button>
        </div>
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        <input value={value("title")} onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          className="w-full border border-slate-300 rounded-md px-3 py-2 font-semibold text-slate-900"
          data-testid={`article-title-${article.handle}`} />
        <textarea value={value("excerpt")} rows={2}
          onChange={(e) => setDraft({ ...draft, excerpt: e.target.value })}
          className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm text-slate-700"
          data-testid={`article-excerpt-${article.handle}`} />
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="font-mono">{article.handle}</span>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={article.published !== false}
              onChange={(e) => save({ published: e.target.checked })}
              className="accent-coral-600" data-testid={`article-published-${article.handle}`} />
            {article.published === false ? "чернова (скрита)" : "публикувана"}
          </label>
          {article.product_handle && <span>продукт: {article.product_handle}</span>}
          <a href={`/articles/${article.handle}`} target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-1 text-slate-600 hover:text-coral-600">
            <ExternalLink className="h-3 w-3" /> виж
          </a>
          <button type="button" onClick={() => save({})} disabled={!dirty || Boolean(busy)}
            className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-40"
            data-testid={`article-save-${article.handle}`}>
            {busy === "save" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Запази
          </button>
        </div>
      </div>
    </div>
  );
};

export default function AdminArticlesPage() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/articles");
      setArticles(data.articles || []);
    } catch (e) { toast.error(formatErr(e)); } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const replace = (updated) =>
    setArticles((cur) => cur.map((a) => (a.handle === updated.handle ? { ...a, ...updated } : a)));

  return (
    <AdminLayout title="Блог статии">
      <p className="text-sm text-slate-500 mb-6 max-w-3xl">
        Смени заглавната снимка, заглавието или краткия текст на всяка статия. Снимката се качва на нашия
        сървър — не се дърпа от Shopify.
      </p>
      {loading ? (
        <p className="text-slate-500">Зареждане…</p>
      ) : (
        <div className="space-y-4" data-testid="admin-articles-list">
          {articles.map((a) => <ArticleRow key={a.handle} article={a} onSaved={replace} />)}
          {!articles.length && <p className="text-slate-500">Още няма статии.</p>}
        </div>
      )}
    </AdminLayout>
  );
}

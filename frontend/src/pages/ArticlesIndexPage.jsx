import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { useSeo } from "../lib/seo";
import { breadcrumbLd, graph, organizationLd, websiteLd } from "../lib/schema";

/** Index of every research article — the header and footer link here, and the sitemap lists it. */
export default function ArticlesIndexPage() {
  const { locale, t, lp } = useLocaleCtx();
  const [articles, setArticles] = useState([]);

  useEffect(() => {
    api.get("/articles", { params: { locale } })
      .then(({ data }) => setArticles(data.articles || []))
      .catch(() => setArticles([]));
  }, [locale]);

  useSeo({
    title: `${t("articles")}`,
    description: t("articlesIndexDesc"),
    locale,
    path: "/pages/articles",
    jsonLd: graph(
      {
        "@type": "CollectionPage",
        name: t("articles"),
        url: `${window.location.origin}${lp("/pages/articles")}`,
        hasPart: articles.slice(0, 50).map((a) => ({
          "@type": "Article",
          headline: a.seo_title || a.title,
          url: `${window.location.origin}${lp(`/articles/${a.handle}`)}`,
        })),
      },
      breadcrumbLd([{ name: t("home"), path: "/" }, { name: t("articles"), path: "/pages/articles" }]),
      organizationLd(),
      websiteLd(locale),
    ),
  });

  return (
    <main className="max-w-5xl mx-auto px-5 sm:px-8 py-14" data-testid="articles-index">
      <nav className="text-xs text-slate-500 mb-6" aria-label="breadcrumb">
        <Link to={lp("/")} className="hover:text-coral-600">{t("home")}</Link>
        <span className="mx-2">/</span>
        <span className="text-slate-700">{t("articles")}</span>
      </nav>
      <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-slate-900">
        {t("articles")}
      </h1>
      <p className="mt-4 text-base text-slate-600 max-w-2xl">{t("articlesIndexDesc")}</p>

      <ul className="mt-12 space-y-px border-y border-slate-200">
        {articles.map((a, i) => (
          <li key={a.handle} className="group" style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}>
            <Link
              to={lp(`/articles/${a.handle}`)}
              className="flex gap-5 py-6 border-b border-slate-100 last:border-0 transition-colors duration-200 hover:bg-slate-50/80"
              data-testid={`articles-index-item-${a.handle}`}
            >
              {a.image && (
                <img
                  src={a.image}
                  alt={a.title}
                  loading="lazy"
                  className="hidden sm:block w-32 h-24 object-cover rounded-lg flex-shrink-0"
                />
              )}
              <div className="min-w-0">
                <h2 className="text-base md:text-lg font-semibold text-slate-900 group-hover:text-coral-600 transition-colors duration-200">
                  {a.title}
                </h2>
                {a.excerpt && <p className="mt-1.5 text-sm text-slate-600 line-clamp-2">{a.excerpt}</p>}
                <p className="mt-2 text-xs text-slate-400">
                  {a.published_at ? new Date(a.published_at).toLocaleDateString(locale === "bg" ? "bg-BG" : undefined) : ""}
                  {a.author ? ` · ${a.author}` : ""}
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      {articles.length === 0 && (
        <p className="mt-12 text-sm text-slate-500" data-testid="articles-index-empty">{t("noResults")}</p>
      )}
    </main>
  );
}

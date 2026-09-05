import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import Layout from "../components/Layout";
import Breadcrumbs from "../components/Breadcrumbs";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { useSeo } from "../lib/seo";
import { graph, breadcrumbLd, organizationLd } from "../lib/schema";
import { isAllCollection } from "../lib/collections";

const SECTIONS = {
  products: { label: "smProducts", key: "products", to: (h) => `/products/${h}` },
  collections: { label: "smCollections", key: "collections", to: (h) => `/collections/${h}` },
  blogs: { label: "smArticles", key: "articles", to: (h) => `/articles/${h}` },
  articles: { label: "smArticles", key: "articles", to: (h) => `/articles/${h}` },
  pages: { label: "smPages", key: "pages", to: (h) => `/pages/${h}` },
};

const HUB = [
  ["/pages/html-sitemap-products", "smProducts"],
  ["/pages/html-sitemap-collections", "smCollections"],
  ["/pages/html-sitemap-blogs", "smArticles"],
  ["/pages/html-sitemap-pages", "smPages"],
];

export default function HtmlSitemapPage() {
  const { pathname } = useLocation();
  const kind = (pathname.match(/html-sitemap-([a-z]+)/) || [])[1];
  const { lp, t, locale } = useLocaleCtx();
  const [index, setIndex] = useState(null);
  const section = SECTIONS[kind];

  useEffect(() => {
    api.get("/link-index").then(({ data }) => {
      const filtered = {
        ...data,
        collections: (data.collections || []).filter((c) => !isAllCollection(c)),
      };
      setIndex(filtered);
    });
  }, [locale]);

  const title = section ? `HTML sitemap — ${t(section.label)}` : "HTML sitemap";
  const path = section ? `/pages/html-sitemap-${kind}` : "/pages/html-sitemap";

  useSeo({
    title: `${title}`,
    description: t("smDesc"),
    locale,
    path,
    jsonLd: graph(
      { "@type": "WebPage", name: title, url: `${window.location.origin}${path}` },
      breadcrumbLd([{ name: t("home"), path: "/" }, { name: title, path }]),
      organizationLd(),
    ),
  });

  const list = (items, to, keyName = "handle") => (
    <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2" data-testid="sitemap-list">
      {items.map((it) => (
        <li key={it[keyName]} className="text-sm">
          <Link to={lp(to(it[keyName]))} className="text-slate-700 hover:text-coral-600 hover:underline underline-offset-4">
            {it.title || it[keyName]}
          </Link>
        </li>
      ))}
    </ul>
  );

  return (
    <Layout>
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 pb-16">
        <Breadcrumbs items={[{ label: "HTML sitemap", to: lp("/pages/html-sitemap") }, ...(section ? [{ label: section.title }] : [])]} />
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mt-4">{title}</h1>

        <div className="flex flex-wrap gap-2 mt-6" data-testid="sitemap-hub-links">
          {HUB.map(([to, labelKey]) => (
            <Link key={to} to={lp(to)}
              className="px-4 py-2 rounded-full border border-slate-200 text-sm text-slate-700 hover:border-coral-500 hover:text-coral-700 transition-colors">
              {t(labelKey)}
            </Link>
          ))}
        </div>

        {!index && <p className="mt-8 text-sm text-slate-400">{t("loadingText")}</p>}

        {index && section && list(index[section.key] || [], section.to, section.key === "pages" ? "slug" : "handle")}

        {index && !section && (
          <div className="mt-8 space-y-10">
            <section>
              <h2 className="text-lg font-bold text-slate-900">{t("smCollections")} ({index.collections.length})</h2>
              {list(index.collections, (h) => `/collections/${h}`)}
            </section>
            <section>
              <h2 className="text-lg font-bold text-slate-900">{t("smProducts")} ({index.products.length})</h2>
              {list(index.products, (h) => `/products/${h}`)}
            </section>
            <section>
              <h2 className="text-lg font-bold text-slate-900">{t("smArticles")} ({index.articles.length})</h2>
              {list(index.articles, (h) => `/articles/${h}`)}
            </section>
            <section>
              <h2 className="text-lg font-bold text-slate-900">{t("smPages")} ({index.pages.length})</h2>
              {list(index.pages, (s) => `/pages/${s}`, "slug")}
            </section>
          </div>
        )}
      </div>
    </Layout>
  );
}

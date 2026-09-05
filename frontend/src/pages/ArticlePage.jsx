import { useEffect, useState } from "react";
import { link } from "../lib/links";
import { useParams, Link } from "react-router-dom";
import Layout, { USPRow } from "../components/Layout";
import Breadcrumbs from "../components/Breadcrumbs";
import ProductCard from "../components/ProductCard";
import { api, img } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { useSeo } from "../lib/seo";
import { graph, articleLd, breadcrumbLd, organizationLd } from "../lib/schema";
import { demoteHeadings } from "../lib/richText";

export default function ArticlePage() {
  const { handle } = useParams();
  const [article, setArticle] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [product, setProduct] = useState(null);
  const [others, setOthers] = useState([]);
  const { lp, t, locale } = useLocaleCtx();

  useEffect(() => {
    api.get("/articles", { params: { locale } })
      .then(({ data }) => setOthers(data.articles || []))
      .catch(() => setOthers([]));
  }, [locale]);

  useEffect(() => {
    setLoaded(false);
    api.get(`/articles/${handle}`, { params: { locale } })
      .then(({ data }) => setArticle(data.article))
      .catch(() => setArticle(null))
      .finally(() => setLoaded(true));
  }, [handle, locale]);

  useEffect(() => {
    setProduct(null);
    if (!article?.product_handle) return;
    api.get(`/products/${article.product_handle}`).then(({ data }) => setProduct(data.product)).catch(() => {});
  }, [article?.product_handle]);

  useSeo({
    title: article ? (article.seo_title || `${article.title}`) : "PurePeptide",
    robots: loaded && !article ? "noindex, follow" : undefined,
    description: article?.seo_description || article?.excerpt || "",
    ogType: "article",
    locale,
    path: `/articles/${handle}`,
    image: article?.image,
    jsonLd: article && graph(
      articleLd({ article, path: `/articles/${handle}` }),
      breadcrumbLd([
        { name: t("home"), path: "/" },
        { name: t("articles"), path: link("articles") },
        { name: article.title, path: `/articles/${handle}` },
      ]),
      organizationLd(),
    ),
  });

  if (!article) {
    // a draft or a retired slug: say so instead of spinning forever
    return (
      <Layout>
        <div className="max-w-3xl mx-auto px-4 py-20 text-center" data-testid="article-not-found">
          {loaded ? (
            <>
              <p className="text-lg font-semibold text-slate-900">{t("articleMissing")}</p>
              <Link to={lp(link("articles"))} className="inline-block mt-4 text-coral-600 font-semibold hover:underline">
                {t("articles")}
              </Link>
            </>
          ) : (
            <p className="text-slate-500">{t("loading")}</p>
          )}
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <article className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 pb-14">
        <Breadcrumbs items={[{ label: t("articles"), to: lp(link("articles")) }, { label: article.title }]} />
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mt-4 leading-tight" data-testid="article-title">
          {article.title}
        </h1>
        <div className="aspect-[16/9] bg-white border border-slate-200 rounded-xl overflow-hidden mt-6">
          <img src={img(article.image, 900)} alt={article.title} className="w-full h-full object-contain" decoding="async" />
        </div>
        <div className="pp-rte mt-8" data-testid="article-body">
          {article.body
            ? <div dangerouslySetInnerHTML={{ __html: demoteHeadings(article.body) }} />
            : <p className="text-lg text-slate-700">{article.excerpt}</p>}
          <p>{t("disclaimer")}</p>
        </div>

        {product && (
          <section className="mt-10">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500 font-bold mb-4">{t("relatedProducts")}</p>
            <div className="max-w-[240px]" data-testid="article-related-product">
              <ProductCard product={product} />
            </div>
          </section>
        )}

        <section className="mt-12 border-t border-slate-200 pt-8">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500 font-bold mb-4">{t("articles")}</p>
          <ul className="space-y-3">
            {others.filter((a) => a.handle !== handle).map((a) => (
              <li key={a.handle}>
                <Link to={lp(`/articles/${a.handle}`)} className="text-slate-800 hover:text-coral-600 underline-offset-4 hover:underline">
                  {a.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </article>
      <USPRow />
    </Layout>
  );
}

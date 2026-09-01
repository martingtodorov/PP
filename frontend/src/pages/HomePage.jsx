import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowLeft, ArrowRight } from "lucide-react";
import Layout, { USPRow } from "../components/Layout";
import ProductsCarousel from "../components/ProductsCarousel";
import PPCalculator from "../components/PPCalculator";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { TRUST_CARDS, FAQ_ITEMS, pick } from "../i18n/locales";
import { useSeo } from "../lib/seo";

const HERO_BG = "/hero-home.png";

const CollectionsCarousel = ({ collections }) => {
  const trackRef = useRef(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(true);
  const { lp } = useLocaleCtx();

  const checkBounds = () => {
    const el = trackRef.current;
    if (!el) return;
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => {
    checkBounds();
    const el = trackRef.current;
    if (!el) return;
    el.addEventListener("scroll", checkBounds, { passive: true });
    window.addEventListener("resize", checkBounds);
    return () => {
      el.removeEventListener("scroll", checkBounds);
      window.removeEventListener("resize", checkBounds);
    };
  }, [collections.length]);

  const scrollBy = (dir) => {
    const el = trackRef.current;
    if (!el) return;
    const card = el.querySelector(".collection-carousel__item");
    const step = card ? card.getBoundingClientRect().width + 8 : el.clientWidth * 0.6;
    el.scrollBy({ left: dir * step, behavior: "smooth" });
  };

  return (
    <div className="collection-carousel" data-testid="collection-list">
      <button type="button" aria-label="Previous" className="collection-carousel__nav collection-carousel__nav--prev"
        onClick={() => scrollBy(-1)} disabled={!canPrev} data-testid="carousel-prev">
        <ArrowLeft className="h-4 w-4" />
      </button>
      <button type="button" aria-label="Next" className="collection-carousel__nav collection-carousel__nav--next"
        onClick={() => scrollBy(1)} disabled={!canNext} data-testid="carousel-next">
        <ArrowRight className="h-4 w-4" />
      </button>
      <div ref={trackRef} className="collection-carousel__track">
        {collections.map((c) => (
          <Link key={c.handle} to={lp(`/collections/${c.handle}`)} className="collection-carousel__item"
            data-testid={`category-${c.handle}`} title={c.title}>
            <div className="collection-carousel__media">
              <img src={c.image} alt={c.title} loading="lazy" />
              <h3 className="collection-carousel__title">{c.title}</h3>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default function HomePage() {
  const [collections, setCollections] = useState([]);
  const [products, setProducts] = useState([]);
  const [articles, setArticles] = useState([]);
  const [settings, setSettings] = useState({});
  const { lp, t, locale } = useLocaleCtx();
  const location = useLocation();

  useEffect(() => {
    Promise.all([
      api.get("/collections"),
      api.get("/products?limit=12"),
      api.get("/articles"),
      api.get("/settings"),
    ]).then(([c, p, a, s]) => {
      setCollections(c.data.collections.filter((x) => (x.base_handle || x.handle) !== "all-peptides"));
      setProducts(p.data.products);
      setArticles(a.data.articles);
      setSettings(s.data);
    });
  }, [locale]);

  useEffect(() => {
    if (!location.hash) return;
    const id = location.hash.slice(1);
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [location]);

  useSeo({
    title: locale === "bg"
      ? "PurePeptide – Nº1 пептиди с доказано качество в България"
      : "PurePeptide – research peptides with verified >99% purity",
    description: t("heroSub"),
    locale,
    path: "/",
  });

  const logos = settings.brand_logos || [];

  return (
    <Layout>
      {/* HERO */}
      <section className="bg-white pt-2 pb-0 sm:pt-5 lg:pt-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:max-w-none lg:px-0">
          <div className="pp-hero pp-hero--bleed" style={{ "--bg": `url('${HERO_BG}')` }} data-testid="hero-section">
            <div className="pp-hero__bg" />
            <div className="pp-hero__overlay" />
            <div className="pp-hero__inner">
              <div className="pp-hero__kicker" data-testid="hero-overline">{t("heroKicker")}</div>
              <h1 className="pp-hero__title" data-testid="hero-title">PurePeptide</h1>
              <h2 className="pp-hero__sub" data-testid="hero-subtitle">{t("heroSub")}</h2>
              <div className="pp-hero__cta">
                <Link to={lp("/collections/all-peptides")} className="pp-hero__btn pp-hero__btn--primary" data-testid="hero-cta-primary">
                  {t("heroCta1")} ›
                </Link>
                <Link to={lp("/pages/chemical-analysis")} className="pp-hero__btn" data-testid="hero-cta-secondary">
                  {t("heroCta2")}
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* LOGO MARQUEE */}
      <section className="mt-3 sm:mt-8" data-testid="logo-marquee">
        <div className="pp-logo-cloud">
          <div className="pp-marquee">
            <div className="pp-track">
              <div className="pp-set">
                {logos.map((src, i) => (
                  <div key={`a-${i}`} className="pp-slide"><img src={src} alt={`Logo ${i + 1}`} loading="eager" /></div>
                ))}
              </div>
              <div className="pp-set" aria-hidden="true">
                {logos.map((src, i) => (
                  <div key={`b-${i}`} className="pp-slide"><img src={src} alt="" loading="eager" /></div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CATEGORIES */}
      <section className="bg-white section--page-width section-resource-list py-5 sm:py-10 lg:py-12">
        <div className="pp-wide">
          <div className="mb-3">
            <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">{t("researchedFor")}</h2>
          </div>
          <CollectionsCarousel collections={collections} />
        </div>
      </section>

      {/* BEST SELLERS */}
      <section className="bg-white section--page-width section-resource-list py-5 sm:py-10 lg:py-12" data-testid="product-list">
        <div className="pp-wide">
          <div className="flex flex-row justify-between items-baseline gap-3 mb-4 sm:mb-6">
            <h2 className="text-xl sm:text-2xl font-semibold text-slate-900 tracking-tight">{t("bestsellers")}</h2>
            <Link to={lp("/collections/all-peptides")}
              className="text-sm font-medium text-slate-700 hover:text-coral-600 underline-offset-4 hover:underline"
              data-testid="view-all-products-btn">
              {t("viewAll")}
            </Link>
          </div>
          <ProductsCarousel products={products} />
        </div>
      </section>

      {/* TRUST PRINCIPLES */}
      <section className="bg-white py-5 sm:py-10 lg:py-12" data-testid="trust-principles">
        <div className="pp-wide grid grid-cols-1 lg:grid-cols-3 gap-5">
          {pick(TRUST_CARDS, locale).map(({ n, title, body }) => (
            <article key={n} className="trust-card" data-testid={`trust-${n}`}>
              <span className="trust-card__num">{n}</span>
              <h3 className="trust-card__title">{title}</h3>
              <p className="trust-card__body">{body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ARTICLES */}
      <section id="articles" className="bg-white scroll-mt-24">
        <div className="pp-wide py-12">
          <div className="flex justify-between items-baseline mb-4">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">{t("articles")}</h2>
            <Link to={lp("/pages/articles")} className="text-sm font-medium text-slate-700 hover:text-coral-600">
              {t("viewAll")}
            </Link>
          </div>
          <div className="grid grid-flow-col auto-cols-[68%] sm:auto-cols-[44%] lg:grid-flow-row lg:grid-cols-5 lg:auto-cols-auto gap-3 lg:gap-5 overflow-x-auto lg:overflow-visible no-scrollbar -mx-4 px-4 lg:mx-0 lg:px-0 pb-2">
            {articles.map((a) => (
              <Link key={a.handle} to={lp(`/articles/${a.handle}`)} className="article-card" data-testid={`article-${a.handle}`}>
                <div className="article-card__media"><img src={a.image} alt={a.title} loading="lazy" /></div>
                <h3 className="article-card__title">{a.title}</h3>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* CALCULATOR */}
      <section className="bg-white pt-2 pb-6 sm:pt-4 sm:pb-12">
        <div className="max-w-[860px] mx-auto px-4 sm:px-6">
          <PPCalculator />
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-slate-50 border-t border-slate-200 scroll-mt-24">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-7 sm:py-14">
          <h2 className="text-3xl sm:text-5xl font-extrabold text-slate-900 text-center mb-6 sm:mb-9 leading-[1.1] tracking-tight">
            {t("faq")}
          </h2>
          <Accordion type="single" collapsible className="space-y-3" data-testid="faq-accordion">
            {pick(FAQ_ITEMS, locale).map((f, i) => (
              <AccordionItem key={i} value={`q${i}`} className="bg-white border border-slate-200 rounded-2xl px-5">
                <AccordionTrigger className="font-semibold text-left text-slate-900 hover:no-underline">{f.q}</AccordionTrigger>
                <AccordionContent className="text-slate-600 leading-relaxed">{f.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      <USPRow />
    </Layout>
  );
}

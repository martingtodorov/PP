import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { FlaskConical, ArrowLeft, ArrowRight } from "lucide-react";
import Layout, { USPRow } from "../components/Layout";
import ProductsCarousel from "../components/ProductsCarousel";
import PPCalculator from "../components/PPCalculator";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import { api } from "../lib/api";

const BRAND_LOGOS = [
  "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/IMG_2354.webp?v=1767538317",
  "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/IMG_2351.webp?v=1767538317",
  "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/IMG_2357.webp?v=1767538316",
  "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/IMG_2353.webp?v=1767538316",
  "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/IMG_2352.webp?v=1767538316",
  "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/IMG_2356.webp?v=1767538317",
  "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/IMG_2355.webp?v=1767538317",
];

const HERO_BG = "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/brand-3_b5f4565b-7bec-41db-9d3b-7bbd1c49e2ac.png?v=1767112972";

const FAQ = [
  { q: "Какво отличава пептидите на PurePeptide?", a: "Прозрачност и контрол на качеството. Всеки продукт е лиофилизиран за по-дълъг срок на съхранение и е преминал HPLC и LC-MS анализ с чистота над 99%. Тестовете се извършват от чешката лаборатория Janoshik. Сертификатите са качени в продуктовите страници." },
  { q: "Как мога да проверя сертификатите за анализ?", a: "Всеки продукт разполага със сертификат за анализ (CoA), извършен от Janoshik Labs. Документите са достъпни директно в продуктовите страници и съдържат партиден номер." },
  { q: "Колко време са стабилни неразтворените пептиди?", a: "В лиофилизиран вид при 2–8°C, защитени от светлина и влага, пептидите запазват стабилност до 24 месеца. При стайна температура – около 4 месеца." },
  { q: "Колко време отнема доставката?", a: "Работим с Еконт. Пратки в България обикновено пристигат в рамките на 1–3 работни дни." },
];

/**
 * _collection-list.liquid `collections_carousel` preset:
 *   layout_type: carousel, columns: 3, mobile_card_size: 44cqw  (≈ 2.3 visible)
 *   placement: below_image, vertical_alignment: center
 *   icons_style: arrow, icons_shape: circle
 *   columns_gap: 8, gap (header→list): 12, padding-block: 48
 */
const CollectionsCarousel = ({ collections }) => {
  const trackRef = useRef(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(true);

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
      <button
        type="button"
        aria-label="Previous"
        className="collection-carousel__nav collection-carousel__nav--prev"
        onClick={() => scrollBy(-1)}
        disabled={!canPrev}
        data-testid="carousel-prev"
      >
        <ArrowLeft className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label="Next"
        className="collection-carousel__nav collection-carousel__nav--next"
        onClick={() => scrollBy(1)}
        disabled={!canNext}
        data-testid="carousel-next"
      >
        <ArrowRight className="h-4 w-4" />
      </button>

      <div ref={trackRef} className="collection-carousel__track">
        {collections.map((c) => (
          <Link
            key={c.handle}
            to={`/collections/${c.handle}`}
            className="collection-carousel__item"
            data-testid={`category-${c.handle}`}
          >
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

  useEffect(() => {
    Promise.all([
      api.get("/collections"),
      api.get("/products?limit=12"),
      api.get("/articles"),
      api.get("/settings"),
    ]).then(([c, p, a, s]) => {
      setCollections(c.data.collections.filter((x) => x.handle !== "all-peptides"));
      setProducts(p.data.products);
      setArticles(a.data.articles);
      setSettings(s.data);
    });
  }, []);

  /* Scroll to #articles or #faq when arriving via mobile-nav hash link */
  const location = useLocation();
  useEffect(() => {
    if (!location.hash) return;
    const id = location.hash.slice(1);
    requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [location]);

  return (
    <Layout>
      {/* HERO */}
      <section className="bg-white pt-6 pb-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="pp-hero" style={{ "--pp-bg": `url('${HERO_BG}')` }} data-testid="hero-section">
            <div className="pp-hero__bg" />
            <div className="pp-hero__overlay" />
            <div className="pp-hero__inner">
              <div className="pp-hero__kicker flex items-center gap-2" data-testid="hero-overline">
                <FlaskConical className="h-4 w-4" />
                лабораторно доказани пептиди
              </div>
              <h1 className="pp-hero__title" data-testid="hero-title">
                {settings.hero_title || "PurePeptide"}
              </h1>
              <p className="pp-hero__sub" data-testid="hero-subtitle">
                {settings.hero_subtitle ||
                  "Лиофилизираните пептиди са златен стандарт за качество и са стабилни до 2 години, за разлика от готовите разтвори със срок около месец. Пептидите ни са тествани от Janoshik Labs."}
              </p>
              <div className="pp-hero__cta">
                <Link to="/collections/all-peptides" className="pp-hero__btn pp-hero__btn--primary" data-testid="hero-cta-primary">
                  {settings.hero_cta_primary || "Пазарувай Пептиди"}
                </Link>
                <Link to="/pages/chemical-analysis" className="pp-hero__btn" data-testid="hero-cta-secondary">
                  {settings.hero_cta_secondary || "Виж Сертификати"}
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* LOGO MARQUEE */}
      <section className="mt-10" data-testid="logo-marquee">
        <div className="pp-logo-cloud">
          <div className="pp-marquee">
            <div className="pp-track">
              <div className="pp-set">
                {BRAND_LOGOS.map((src, i) => (
                  <div key={`a-${i}`} className="pp-slide"><img src={src} alt={`Logo ${i + 1}`} loading="eager" /></div>
                ))}
              </div>
              <div className="pp-set" aria-hidden="true">
                {BRAND_LOGOS.map((src, i) => (
                  <div key={`b-${i}`} className="pp-slide"><img src={src} alt="" loading="eager" /></div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* COLLECTION-LIST · carousel preset */}
      <section className="bg-white section--page-width section-resource-list" style={{ paddingBlock: "48px" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* group header — content_direction: column, gap: 12, padding-block-end: 16 (text) */}
          <div className="mb-4">
            <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">
              Пазарувай по категория
            </h2>
          </div>
          <CollectionsCarousel collections={collections} />
        </div>
      </section>

      {/* PRODUCT-LIST · products_grid preset */}
      <section className="bg-slate-50 border-y border-slate-200 section--page-width section-resource-list" style={{ paddingBlock: "48px" }} data-testid="product-list">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* _product-list-content header: row · space-between · flex-end · align_baseline · gap 12 */}
          <div className="flex flex-row justify-between items-baseline gap-3 mb-7">
            <h3 className="text-xl sm:text-2xl font-semibold text-slate-900 tracking-tight">
              Най-продавани пептиди
            </h3>
            <Link
              to="/collections/all-peptides"
              className="text-sm font-medium text-slate-700 hover:text-coral-600 underline-offset-4 hover:underline"
              data-testid="view-all-products-btn"
            >
              Виж всички
            </Link>
          </div>
          {/* resource-list-grid → carousel layout per `products_carousel` preset */}
          <ProductsCarousel products={products} />
        </div>
      </section>

      {/* PP CALCULATOR */}
      <section className="bg-white" style={{ paddingBlock: "48px" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <PPCalculator />
        </div>
      </section>

      {/* TRUST PRINCIPLES — numbered cards stacked on mobile */}
      <section className="bg-white" style={{ paddingBlock: "16px 48px" }} data-testid="trust-principles">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 lg:grid-cols-3 gap-5">
          {[
            {
              n: "01",
              title: "Документация преди обещания",
              body: "Вярваме, че доверието започва от ясната информация. Затова PurePeptide поставя акцент върху лабораторни анализи и научни източници, вместо върху преувеличени твърдения.",
            },
            {
              n: "02",
              title: "Научен и неутрален подход",
              body: "Описанията ни са изградени около публикувана научна литература, изследователски контекст и неутрален език. Целта е информацията да бъде полезна, точна и ясна.",
            },
            {
              n: "03",
              title: "Качество и прозрачност",
              body: "Всеки партиден номер преминава HPLC и LC-MS анализ от независимата лаборатория Janoshik. Сертификатите са достъпни директно в продуктовите страници.",
            },
          ].map(({ n, title, body }) => (
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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mb-6">Научни Статии</h2>
          <div className="grid grid-flow-col auto-cols-[68%] sm:auto-cols-[44%] lg:grid-flow-row lg:grid-cols-4 lg:auto-cols-auto gap-3 lg:gap-5 overflow-x-auto lg:overflow-visible no-scrollbar -mx-4 px-4 lg:mx-0 lg:px-0 pb-2">
            {articles.map((a) => (
              <article key={a.handle} className="article-card" data-testid={`article-${a.handle}`}>
                <div className="article-card__media">
                  <img src={a.image} alt={a.title} loading="lazy" />
                </div>
                <h3 className="article-card__title">{a.title}</h3>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-slate-50 border-t border-slate-200 scroll-mt-24">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <h2 className="text-3xl sm:text-5xl font-extrabold text-slate-900 text-center mb-10 leading-[1.1] tracking-tight">
            Имате въпроси?<br />Ето отговорите
          </h2>
          <Accordion type="single" collapsible className="space-y-3" data-testid="faq-accordion">
            {FAQ.map((f, i) => (
              <AccordionItem key={i} value={`q${i}`} className="bg-white border border-slate-200 rounded-2xl px-5">
                <AccordionTrigger className="font-semibold text-left text-slate-900 hover:no-underline">{f.q}</AccordionTrigger>
                <AccordionContent className="text-slate-600 leading-relaxed">{f.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      {/* USP — moved to bottom per reference */}
      <USPRow />
    </Layout>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight, FlaskConical, ShieldCheck, FileCheck2 } from "lucide-react";
import Layout, { USPRow } from "../components/Layout";
import ProductCard from "../components/ProductCard";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";

const FAQ = [
  {
    q: "Какво отличава пептидите на PurePeptide?",
    a: "Прозрачност и контрол на качеството. Всеки продукт е лиофилизиран за по-дълъг срок на съхранение и е преминал HPLC и LC-MS анализ с чистота над 99%. Тестовете се извършват от чешката лаборатория Janoshik. Сертификатите са качени в продуктовите страници.",
  },
  {
    q: "Как мога да проверя сертификатите за анализ?",
    a: "Всеки продукт разполага със сертификат за анализ (CoA), извършен от Janoshik Labs. Документите са достъпни директно в продуктовите страници и съдържат партиден номер.",
  },
  {
    q: "Колко време са стабилни неразтворените пептиди?",
    a: "В лиофилизиран вид при 2–8°C, защитени от светлина и влага, пептидите запазват стабилност до 24 месеца. При стайна температура – около 4 месеца.",
  },
  {
    q: "Колко време отнема доставката?",
    a: "Работим с Еконт. Пратки в България обикновено пристигат в рамките на 1–3 работни дни.",
  },
];

const CalcSection = () => {
  const [pep, setPep] = useState(5);
  const [vol, setVol] = useState(2);
  const [dose, setDose] = useState(250);
  const concPerMl = (pep * 1000) / vol; // mcg/ml
  const ml = dose / concPerMl;
  return (
    <section className="bg-slate-50 border-y border-slate-200" data-testid="calculator-section">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 grid lg:grid-cols-2 gap-12 items-center">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-blue-600 font-bold">Инструмент</p>
          <h2 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900 mt-3 leading-tight">Калкулатор за концентрация</h2>
          <p className="text-slate-600 mt-4 leading-relaxed max-w-md">
            Изчислете точно нужния обем разтвор за желаната доза пептид. За научни и лабораторни цели.
          </p>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-8 space-y-5">
          <div>
            <label className="text-sm font-medium text-slate-700">Количество пептид <span className="text-slate-400">(mg)</span></label>
            <input type="number" min="0" step="0.1" value={pep} onChange={(e) => setPep(Number(e.target.value))} className="mt-1.5 block w-full border border-slate-300 rounded-md p-3 focus:ring-blue-500 focus:border-blue-500" data-testid="calc-pep" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Обем разтвор <span className="text-slate-400">(mL)</span></label>
            <input type="number" min="0" step="0.1" value={vol} onChange={(e) => setVol(Number(e.target.value))} className="mt-1.5 block w-full border border-slate-300 rounded-md p-3 focus:ring-blue-500 focus:border-blue-500" data-testid="calc-vol" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Желана доза <span className="text-slate-400">(mcg)</span></label>
            <input type="number" min="0" step="1" value={dose} onChange={(e) => setDose(Number(e.target.value))} className="mt-1.5 block w-full border border-slate-300 rounded-md p-3 focus:ring-blue-500 focus:border-blue-500" data-testid="calc-dose" />
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-5 flex items-baseline justify-between">
            <span className="text-sm text-blue-900 font-medium">Нужен обем</span>
            <span className="font-display font-extrabold text-3xl text-blue-700" data-testid="calc-result">{isFinite(ml) ? ml.toFixed(2) : "0.00"} mL</span>
          </div>
        </div>
      </div>
    </section>
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

  return (
    <Layout>
      {/* HERO */}
      <section className="relative overflow-hidden bg-white">
        <div className="absolute inset-0 bg-grid opacity-60 pointer-events-none" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-28 grid lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7">
            <p className="text-xs uppercase tracking-[0.25em] text-blue-600 font-bold flex items-center gap-2" data-testid="hero-overline">
              <FlaskConical className="h-4 w-4" /> лабораторно доказани пептиди
            </p>
            <h1 className="mt-5 font-display font-extrabold text-5xl sm:text-6xl lg:text-7xl tracking-tight text-slate-900 leading-[1.05]" data-testid="hero-title">
              {settings.hero_title || "PurePeptide"}
            </h1>
            <p className="mt-6 text-lg text-slate-600 leading-relaxed max-w-2xl" data-testid="hero-subtitle">
              {settings.hero_subtitle ||
                "Лиофилизираните пептиди са златен стандарт за качество и са стабилни до 2 години, за разлика от готовите разтвори със срок около месец."}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/collections/all-peptides">
                <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="hero-cta-primary">
                  {settings.hero_cta_primary || "Пазарувай Пептиди"} <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Button size="lg" variant="outline" className="border-slate-300" data-testid="hero-cta-secondary">
                {settings.hero_cta_secondary || "Виж Сертификати"}
              </Button>
            </div>
            <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-sm text-slate-600">
              <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-blue-600" /> &gt;99% чистота HPLC</span>
              <span className="flex items-center gap-2"><FileCheck2 className="h-4 w-4 text-blue-600" /> Janoshik CoA</span>
              <span className="flex items-center gap-2"><FlaskConical className="h-4 w-4 text-blue-600" /> Лиофилизирани</span>
            </div>
          </div>
          <div className="lg:col-span-5 relative">
            <div className="aspect-[4/5] rounded-2xl overflow-hidden bg-slate-100 border border-slate-200">
              <img
                src="https://images.unsplash.com/photo-1579154341184-22069e4614d2?auto=format&fit=crop&w=1200&q=80"
                alt="Лаборатория"
                className="w-full h-full object-cover"
              />
            </div>
            <div className="absolute -bottom-6 -left-6 bg-white border border-slate-200 rounded-xl p-4 shadow-sm hidden sm:block">
              <p className="text-[10px] uppercase tracking-widest text-blue-600 font-bold">Janoshik Labs</p>
              <p className="font-display font-bold text-slate-900 text-2xl mt-1">99.4%</p>
              <p className="text-xs text-slate-500">средна чистота на партидите</p>
            </div>
          </div>
        </div>
      </section>

      <USPRow />

      {/* CATEGORIES */}
      <section className="bg-white" data-testid="category-grid">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="flex items-end justify-between mb-10">
            <h2 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900">Пазарувай по категория</h2>
            <Link to="/collections/all-peptides" className="text-sm font-semibold text-blue-600 hover:text-blue-700 inline-flex items-center gap-1">
              Всички <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {collections.map((c) => (
              <Link
                key={c.handle}
                to={`/collections/${c.handle}`}
                className="group relative aspect-square rounded-xl overflow-hidden border border-slate-200 bg-slate-50"
                data-testid={`category-${c.handle}`}
              >
                <img src={c.image} alt={c.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 via-slate-900/10 to-transparent" />
                <div className="absolute bottom-0 left-0 right-0 p-4">
                  <p className="font-display font-bold text-white text-lg">{c.title}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* BEST SELLERS */}
      <section className="bg-slate-50 border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="flex items-end justify-between mb-10">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-blue-600 font-bold mb-2">Най-търсени</p>
              <h2 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900">Най-продавани пептиди</h2>
            </div>
            <Link to="/collections/all-peptides" className="text-sm font-semibold text-blue-600 hover:text-blue-700 inline-flex items-center gap-1">
              Всички <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
            {products.slice(0, 8).map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        </div>
      </section>

      <CalcSection />

      {/* ARTICLES */}
      <section className="bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <h2 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900 mb-10">Научни статии</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {articles.map((a) => (
              <article key={a.handle} className="bg-white border border-slate-200 rounded-xl overflow-hidden hover:shadow-md transition-shadow" data-testid={`article-${a.handle}`}>
                <div className="aspect-[4/3] bg-slate-50 overflow-hidden">
                  <img src={a.image} alt={a.title} className="w-full h-full object-cover" />
                </div>
                <div className="p-5">
                  <h3 className="font-display font-semibold text-slate-900 leading-snug line-clamp-3">{a.title}</h3>
                  <p className="text-sm text-slate-500 mt-2 line-clamp-2">{a.excerpt}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-slate-50 border-t border-slate-200">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <p className="text-xs uppercase tracking-[0.2em] text-blue-600 font-bold text-center mb-3">Имате въпроси?</p>
          <h2 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900 text-center mb-10">Ето отговорите</h2>
          <Accordion type="single" collapsible className="space-y-3" data-testid="faq-accordion">
            {FAQ.map((f, i) => (
              <AccordionItem key={i} value={`q${i}`} className="bg-white border border-slate-200 rounded-xl px-5">
                <AccordionTrigger className="font-display font-semibold text-left text-slate-900 hover:no-underline">{f.q}</AccordionTrigger>
                <AccordionContent className="text-slate-600 leading-relaxed">{f.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>
    </Layout>
  );
}

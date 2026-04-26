import { useParams, Link } from "react-router-dom";
import { ShieldCheck, FileCheck2, FlaskConical, Users, ArrowRight } from "lucide-react";
import Layout from "../components/Layout";

const PAGES = {
  "what-are-peptides": {
    title: "Какво са пептиди?",
    overline: "Основи",
    icon: FlaskConical,
    body: [
      "Пептидите са къси вериги от аминокиселини, свързани с пептидни връзки. Те се срещат естествено в организма и изпълняват разнообразни роли — от регулация на хормоналните системи до тъканна регенерация и имунен отговор.",
      "Лиофилизираните (изсушени чрез замразяване) пептиди се отличават с по-голяма стабилност в сравнение с готовите разтвори. При правилно съхранение лиофилизатите могат да запазят чистотата си до 24 месеца.",
      "Продуктите на PurePeptide са предназначени единствено за научноизследователски цели и не са медицински изделия.",
    ],
    cta: { label: "Виж сертификати", to: "/pages/chemical-analysis" },
  },
  "chemical-analysis": {
    title: "Химичен анализ",
    overline: "Качество",
    icon: ShieldCheck,
    body: [
      "Всеки производствен партиден номер преминава анализ от независимата чешка лаборатория Janoshik Labs.",
      "Извършват се HPLC (High-Performance Liquid Chromatography) и LC-MS (Liquid Chromatography – Mass Spectrometry) анализи. Стандартът ни е чистота над 99%.",
      "Сертификатите за анализ (CoA) са достъпни директно в продуктовите страници и съдържат партиден номер, дата и резултат.",
    ],
    cta: { label: "Към каталога", to: "/collections/all-peptides" },
  },
  partners: {
    title: "Партньори",
    overline: "Сътрудничество",
    icon: Users,
    body: [
      "Janoshik Labs (Чехия) — независим лабораторен партньор, извършващ HPLC и LC-MS анализите ни.",
      "Еконт — куриерски партньор за експресна доставка в България и наложен платеж.",
      "Заинтересувани сте от B2B сътрудничество? Свържете се с нас на info@purepeptide.bg.",
    ],
    cta: { label: "Свържи се", to: "mailto:info@purepeptide.bg", external: true },
  },
};

export default function StaticPage() {
  const { slug } = useParams();
  const page = PAGES[slug];

  if (!page) {
    return (
      <Layout>
        <div className="max-w-3xl mx-auto px-4 py-20 text-center">
          <h1 className="text-3xl font-bold text-slate-900">Страницата не е намерена</h1>
          <Link to="/" className="text-coral-600 mt-4 inline-block">← Към началото</Link>
        </div>
      </Layout>
    );
  }

  const Icon = page.icon || FileCheck2;

  return (
    <Layout>
      <div className="bg-slate-50 border-b border-slate-200">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <p className="text-xs uppercase tracking-[0.2em] text-coral-600 font-bold mb-3" data-testid={`page-overline-${slug}`}>
            {page.overline}
          </p>
          <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 tracking-tight" data-testid={`page-title-${slug}`}>
            {page.title}
          </h1>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="flex items-start gap-5">
          <div className="w-12 h-12 bg-coral-50 text-coral-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <Icon className="h-6 w-6" strokeWidth={1.5} />
          </div>
          <div className="flex-1 space-y-5 text-slate-700 leading-relaxed">
            {page.body.map((p, i) => <p key={i}>{p}</p>)}
            {page.cta && (
              <div className="pt-4">
                {page.cta.external ? (
                  <a href={page.cta.to} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-coral-600 text-white font-semibold hover:bg-coral-700">
                    {page.cta.label} <ArrowRight className="h-4 w-4" />
                  </a>
                ) : (
                  <Link to={page.cta.to} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-coral-600 text-white font-semibold hover:bg-coral-700">
                    {page.cta.label} <ArrowRight className="h-4 w-4" />
                  </Link>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

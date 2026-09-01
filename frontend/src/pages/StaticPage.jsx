import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import Layout, { USPRow } from "../components/Layout";
import Breadcrumbs from "../components/Breadcrumbs";
import PPCalculator from "../components/PPCalculator";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { FAQ_ITEMS, pick } from "../i18n/locales";
import { useSeo } from "../lib/seo";
import { ContactForm } from "../components/ContactForm";
import { graph, faqLd, breadcrumbLd, organizationLd } from "../lib/schema";

const BODY = {
  bg: {
    "what-are-peptides": {
      title: "Какво са пептидите?",
      html: "<p>Пептидите са къси вериги от аминокиселини, свързани чрез пептидни връзки. В организма те действат като сигнални молекули и участват в регулацията на метаболизъм, възстановяване на тъкани, имунен отговор и много други процеси.</p><h2>Лиофилизирана форма</h2><p>Всички наши пептиди се доставят в лиофилизирана (изсушена чрез замразяване) форма. Тя запазва структурата и биологичната активност значително по-дълго от готовите водни разтвори.</p><h2>Изследователска употреба</h2><p>Продуктите са предназначени изключително за лабораторни и научноизследователски цели.</p>",
    },
    "chemical-analysis": {
      title: "Химичен анализ и сертификати",
      html: "<p>Всяка партида преминава HPLC и LC-MS анализ в независимата чешка лаборатория <strong>Janoshik Analytical</strong>. Анализът потвърждава идентичност, чистота (&gt;99%) и съдържание на пептида.</p><h2>Какво съдържа сертификатът</h2><ul><li>Партиден номер и дата на анализ</li><li>HPLC хроматограма с процент чистота</li><li>Масспектрометрично потвърждение на молекулната маса</li><li>Съдържание на нетен пептид</li></ul>",
    },
    contacts: {
      title: "Контакти",
      html: "<p>Свържете се с нас за въпроси относно продукти, поръчки и доставки.</p><p>Имейл: <a href='mailto:info@purepeptide.bg'>info@purepeptide.bg</a><br>Работно време: понеделник – петък, 9:00 – 18:00</p><p>Доставки се извършват със Спиди в рамките на 1–3 работни дни.</p>",
    },
    partners: {
      title: "Партньори",
      html: "<p>Работим с независими лаборатории и научни партньори, които подпомагат контрола на качеството и достоверността на публикуваната информация.</p><ul><li>Janoshik Analytical — HPLC / LC-MS анализи</li><li>Специализирани дистрибутори за научни консумативи</li></ul><p>За партньорски запитвания ни пишете на info@purepeptide.bg.</p>",
    },
    "privacy-policy": { title: "Политика за поверителност", html: "<p>Обработваме лични данни само за изпълнение на поръчки и комуникация, свързана с тях. Не предоставяме данни на трети страни извън необходимите за доставка партньори.</p>" },
    "refund-policy": { title: "Правила за възстановяване на суми", html: "<p>Приемаме връщане на неотворени продукти в оригинална опаковка в рамките на 14 дни от получаването. Възстановяването се извършва по същия начин на плащане.</p>" },
    "terms-of-service": { title: "Общи условия", html: "<p>Използвайки този сайт, потвърждавате, че сте на възраст над 18 години и че поръчвате продуктите изключително за лабораторни и научноизследователски цели. Продуктите не са лекарствени средства.</p>" },
    "shipping-policy": { title: "Условия за доставка", html: "<p>Поръчките се обработват в рамките на 1–3 работни дни и се изпращат със Спиди до офис или адрес. Получавате имейл с товарителница след изпращане.</p>" },
  },
  en: {
    "what-are-peptides": {
      title: "What are peptides?",
      html: "<p>Peptides are short chains of amino acids linked by peptide bonds. In the body they act as signalling molecules involved in metabolism, tissue repair, immune response and many other processes.</p><h2>Lyophilised form</h2><p>All of our peptides ship lyophilised (freeze-dried), which preserves structure and biological activity far longer than pre-mixed aqueous solutions.</p><h2>Research use</h2><p>All products are intended strictly for laboratory and research purposes.</p>",
    },
    "chemical-analysis": {
      title: "Laboratory analysis & certificates",
      html: "<p>Every batch undergoes HPLC and LC-MS analysis at the independent Czech laboratory <strong>Janoshik Analytical</strong>, confirming identity, purity (&gt;99%) and net peptide content.</p><h2>What the certificate contains</h2><ul><li>Batch number and analysis date</li><li>HPLC chromatogram with purity percentage</li><li>Mass-spectrometry confirmation of molecular weight</li><li>Net peptide content</li></ul>",
    },
    contacts: { title: "Contact", html: "<p>Get in touch about products, orders and shipping.</p><p>Email: <a href='mailto:info@purepeptide.eu'>info@purepeptide.eu</a><br>Hours: Monday – Friday, 9:00 – 18:00 CET</p>" },
    partners: { title: "Partners", html: "<p>We work with independent laboratories and research partners supporting quality control and the accuracy of the published information.</p><ul><li>Janoshik Analytical — HPLC / LC-MS testing</li><li>Specialised distributors of research consumables</li></ul>" },
    "privacy-policy": { title: "Privacy policy", html: "<p>We process personal data only to fulfil orders and related communication. Data is never shared beyond the partners required for delivery.</p>" },
    "refund-policy": { title: "Refund policy", html: "<p>Unopened products in original packaging can be returned within 14 days of delivery. Refunds are issued via the original payment method.</p>" },
    "terms-of-service": { title: "Terms of service", html: "<p>By using this site you confirm that you are over 18 and that you purchase the products strictly for laboratory and research purposes. The products are not medicinal products.</p>" },
    "shipping-policy": { title: "Shipping policy", html: "<p>Orders are processed within 1–3 business days and shipped with a tracked courier. A tracking email is sent once the parcel leaves our facility.</p>" },
  },
};

export default function StaticPage() {
  const { slug } = useParams();
  const { lp, t, locale } = useLocaleCtx();
  const [articles, setArticles] = useState([]);
  const [collections, setCollections] = useState([]);
  const [remote, setRemote] = useState(null);

  useEffect(() => {
    api.get("/articles").then(({ data }) => setArticles(data.articles));
    api.get("/collections").then(({ data }) => setCollections(data.collections.filter((c) => (c.base_handle || c.handle) !== "all-peptides")));
  }, [locale]);

  useEffect(() => {
    setRemote(null);
    api.get(`/pages/${slug}`).then(({ data }) => setRemote(data.page)).catch(() => setRemote(null));
  }, [slug, locale]);

  const table = BODY[locale] || BODY.en;
  const fallback = table[slug] || BODY.en[slug] || null;
  const page = remote?.title || remote?.html ? remote : fallback;
  const isFaq = slug === "faq";
  const isArticles = slug === "articles";
  const faqItems = remote?.faq_items?.length ? remote.faq_items : pick(FAQ_ITEMS, locale);
  const title = isArticles ? t("articles") : remote?.title || (isFaq ? t("faq") : page?.title) || slug;

  useSeo({
    title: remote?.seo_title || `${title} | PurePeptide`,
    description:
      remote?.seo_description ||
      (page?.html || "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim().slice(0, 155),
    locale,
    path: `/pages/${slug}`,
    jsonLd: graph(
      isFaq && faqItems.length ? faqLd(faqItems) : {
        "@type": "WebPage",
        name: title,
        url: `${window.location.origin}/pages/${slug}`,
        isPartOf: { "@id": `${window.location.origin}/#website` },
      },
      breadcrumbLd([
        { name: "Начало", path: "/" },
        { name: title, path: `/pages/${slug}` },
      ]),
      organizationLd(),
    ),
  });

  return (
    <Layout>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 pb-14">
        <Breadcrumbs items={[{ label: title }]} />
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mt-4">{title}</h1>

        {isFaq && (remote?.faq_items?.length > 0 || !remote?.html) && (
          <Accordion type="single" collapsible className="space-y-3 mt-8" data-testid="static-faq">
            {faqItems.map((f, i) => (
              <AccordionItem key={i} value={`q${i}`} className="bg-white border border-slate-200 rounded-2xl px-5">
                <AccordionTrigger className="font-semibold text-left text-slate-900 hover:no-underline">{f.q}</AccordionTrigger>
                <AccordionContent className="text-slate-600 leading-relaxed">{f.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}

        {isArticles && (
          <ul className="mt-8 space-y-6" data-testid="articles-index">
            {articles.map((a) => (
              <li key={a.handle} className="flex gap-4">
                <Link to={lp(`/articles/${a.handle}`)} className="w-28 h-20 flex-shrink-0 bg-white border border-slate-200 rounded-lg overflow-hidden">
                  <img src={a.image} alt={a.title} className="w-full h-full object-contain" />
                </Link>
                <div>
                  <Link to={lp(`/articles/${a.handle}`)} className="font-semibold text-slate-900 hover:text-coral-600">
                    {a.title}
                  </Link>
                  <p className="text-sm text-slate-500 mt-1 line-clamp-2">{a.excerpt}</p>
                </div>
              </li>
            ))}
          </ul>
        )}

        {page?.html && !isArticles && (
          <div className="pp-rte mt-6" dangerouslySetInnerHTML={{ __html: page.html }} data-testid="static-body" />
        )}

        {slug === "contacts" && <ContactForm />}

        {slug === "what-are-peptides" && (
          <div className="mt-10">
            <PPCalculator />
          </div>
        )}

        {/* internal link hub */}
        <section className="mt-12 border-t border-slate-200 pt-8">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500 font-bold mb-4">{t("shopByCategory")}</p>
          <div className="flex flex-wrap gap-2" data-testid="static-collection-links">
            {collections.map((c) => (
              <Link key={c.handle} to={lp(`/collections/${c.handle}`)}
                className="px-4 py-2 rounded-full border border-slate-200 text-sm text-slate-700 hover:border-coral-600 hover:text-coral-700 transition-colors">
                {c.title}
              </Link>
            ))}
          </div>
        </section>
      </div>
      <USPRow />
    </Layout>
  );
}

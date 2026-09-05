import { useLocaleCtx } from "../i18n/LocaleContext";
import { Link } from "react-router-dom";
import { link } from "../lib/links";

/* A removed or rotated URL is a dead end on purpose: the server answers 404 and the page stays on
   that URL. No client-side hop to the catalogue — that would turn every retired handle into a
   soft 200 for crawlers that execute JavaScript. */
export const NotFoundBlock = () => {
  const { lp, t } = useLocaleCtx();

  return (
    <div className="max-w-2xl mx-auto px-4 py-32 text-center" data-testid="not-found-block">
      <p className="text-sm font-semibold tracking-[0.2em] text-coral-600">404</p>
      <h1 className="text-2xl font-bold text-slate-900 tracking-tight mt-4">{t("notFoundTitle")}</h1>
      <p className="text-slate-600 mt-2">{t("notFoundText")}</p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          to={lp(link("catalog"))}
          data-testid="not-found-catalog-link"
          className="inline-flex items-center rounded-md bg-coral-600 px-5 py-3 text-white font-medium shadow-sm transition-transform duration-200 hover:-translate-y-0.5"
        >
          {t("allPeptides")}
        </Link>
        <Link
          to={lp("/")}
          data-testid="not-found-home-link"
          className="inline-flex items-center rounded-md border border-slate-200 px-5 py-3 text-slate-700 font-medium transition-colors duration-200 hover:bg-slate-50"
        >
          {t("home")}
        </Link>
      </div>
    </div>
  );
};

export default NotFoundBlock;

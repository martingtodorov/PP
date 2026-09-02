import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { link, setLinks } from "../lib/links";
import { useLocaleCtx } from "../i18n/LocaleContext";

/* A removed or rotated URL sends the visitor straight to "all peptides" instead of a dead end.
   The catalogue path is re-read from /api/links so a rotated handle can never redirect onto itself. */
export const NotFoundBlock = () => {
  const { lp, t, locale } = useLocaleCtx();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    const go = (path) => {
      if (cancelled) return;
      const target = lp(path);
      navigate(target === window.location.pathname ? lp("/") : target, { replace: true });
    };
    api.get(`/links?locale=${locale}`)
      .then(({ data }) => { setLinks(data); go(data.catalog || link("catalog")); })
      .catch(() => go("/"));
    return () => { cancelled = true; };
  }, [locale]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="max-w-2xl mx-auto px-4 py-32 text-center" data-testid="not-found-block">
      <Loader2 className="h-8 w-8 text-coral-600 mx-auto animate-spin" />
      <h1 className="text-2xl font-bold text-slate-900 tracking-tight mt-6">{t("notFoundTitle")}</h1>
      <p className="text-slate-600 mt-2">{t("notFoundText")}</p>
    </div>
  );
};

export default NotFoundBlock;

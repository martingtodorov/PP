import { useEffect, useRef, useState } from "react";
import { Globe, Check } from "lucide-react";
import { LOCALES, LOCALE_META } from "../i18n/locales";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { rememberLocale } from "../i18n/geoLocale";

/** Language button + dropdown, shown on every domain. The choice is remembered so the
 *  purepeptide.eu apex never overrides it with the IP country again. */
export const LocaleSwitcher = ({ testId = "locale-switcher" }) => {
  const { locale, localeUrl, basePath } = useLocaleCtx();
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const enabled = LOCALES.filter((l) => LOCALE_META[l].enabled !== false);

  return (
    <div className="relative" ref={box}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 p-2 rounded-md text-slate-800 hover:bg-slate-50 transition-colors"
        aria-label={LOCALE_META[locale]?.label || locale}
        aria-expanded={open}
        data-testid={testId}
      >
        <Globe className="h-5 w-5" strokeWidth={1.8} />
        <span className="text-xs font-bold uppercase tracking-wider">{locale}</span>
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 w-52 max-h-[70vh] overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-xl py-1.5 z-50"
          data-testid={`${testId}-menu`}
        >
          {enabled.map((l) => (
            <a
              key={l}
              href={localeUrl(l, basePath)}
              hrefLang={LOCALE_META[l].hreflang}
              onClick={() => rememberLocale(l)}
              className={`flex items-center justify-between gap-2 px-4 py-2 text-sm transition-colors ${
                l === locale ? "text-coral-700 font-semibold bg-coral-50" : "text-slate-700 hover:bg-slate-50"
              }`}
              data-testid={`${testId}-${l}`}
            >
              {LOCALE_META[l].label}
              {l === locale && <Check className="h-4 w-4" />}
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

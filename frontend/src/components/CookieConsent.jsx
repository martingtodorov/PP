import { useEffect, useState } from "react";
import { link } from "../lib/links";
import { Link } from "react-router-dom";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { cookieText } from "../i18n/cookies";

const KEY = "pp_cookie_consent_v1";
const SIX_MONTHS = 180 * 24 * 60 * 60;

const store = (value) => {
  try {
    window.localStorage.setItem(KEY, JSON.stringify({ ...value, at: Date.now() }));
    document.cookie = `pp_consent=${value.analytics ? 1 : 0}${value.marketing ? 1 : 0};max-age=${SIX_MONTHS};path=/;SameSite=Lax`;
  } catch (e) { /* ignore */ }
  window.dispatchEvent(new CustomEvent("pp:consent", { detail: value }));
};

const Toggle = ({ on, disabled, onChange, testId }) => (
  <button
    type="button"
    role="switch"
    aria-checked={on}
    disabled={disabled}
    onClick={() => onChange(!on)}
    data-testid={testId}
    className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${on ? "bg-coral-600" : "bg-slate-300"} ${disabled ? "opacity-50" : ""}`}
  >
    <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${on ? "translate-x-5" : ""}`} />
  </button>
);

export const CookieConsent = () => {
  const { lp, locale } = useLocaleCtx();
  const c = cookieText(locale);
  const [open, setOpen] = useState(false);
  const [panel, setPanel] = useState(false);
  const [prefs, setPrefs] = useState({ functional: true, analytics: true, marketing: true });

  useEffect(() => {
    try {
      if (!window.localStorage.getItem(KEY)) setOpen(true);
    } catch (e) {
      setOpen(true);
    }
  }, []);

  // the banner owns the bottom of the viewport until the visitor decides
  useEffect(() => {
    document.body.classList.toggle("pp-consent-open", open);
    return () => document.body.classList.remove("pp-consent-open");
  }, [open]);

  if (!open) return null;

  const decide = (value) => {
    store({ necessary: true, ...value });
    setOpen(false);
  };

  const rows = [
    { key: "necessary", locked: true },
    { key: "functional" },
    { key: "analytics" },
    { key: "marketing" },
  ];

  return (
    <div className="pp-cookie" role="dialog" aria-live="polite" aria-label={c.title} data-testid="cookie-banner">
      <div className="pp-cookie__card">
        <div className="pp-cookie__body">
          <h2 className="pp-cookie__title" data-testid="cookie-title">{c.title}</h2>
          <p className="pp-cookie__text">
            {c.body}{" "}
            <Link to={lp(link("terms"))} className="underline hover:text-coral-600" data-testid="cookie-privacy-link">
              {c.privacy}
            </Link>
          </p>

          {panel && (
            <div className="pp-cookie__prefs" data-testid="cookie-preferences">
              {rows.map((r) => (
                <div key={r.key} className="pp-cookie__row">
                  <div className="min-w-0">
                    <p className="pp-cookie__row-title">
                      {c[r.key]}
                      {r.locked && <span className="pp-cookie__badge">{c.always}</span>}
                    </p>
                    <p className="pp-cookie__row-desc">{c[`${r.key}Desc`]}</p>
                  </div>
                  <Toggle
                    on={r.locked ? true : prefs[r.key]}
                    disabled={r.locked}
                    onChange={(v) => setPrefs((p) => ({ ...p, [r.key]: v }))}
                    testId={`cookie-toggle-${r.key}`}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="pp-cookie__actions">
          {panel ? (
            <button type="button" className="pp-cookie__btn pp-cookie__btn--ghost"
              onClick={() => decide(prefs)} data-testid="cookie-save">
              {c.save}
            </button>
          ) : (
            <button type="button" className="pp-cookie__btn pp-cookie__btn--ghost"
              onClick={() => setPanel(true)} data-testid="cookie-customize">
              {c.customize}
            </button>
          )}
          <button type="button" className="pp-cookie__btn pp-cookie__btn--outline"
            onClick={() => decide({ functional: false, analytics: false, marketing: false })}
            data-testid="cookie-reject">
            {c.reject}
          </button>
          <button type="button" className="pp-cookie__btn pp-cookie__btn--solid"
            onClick={() => decide({ functional: true, analytics: true, marketing: true })}
            data-testid="cookie-accept">
            {c.accept}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CookieConsent;

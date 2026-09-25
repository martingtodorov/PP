import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { initConsentDefaults, updateConsent, measurementId, loadGa, pageView, hasAnalyticsConsent }
  from "../lib/ga4";

/** Loads GA4 with the ID from the shop settings, after cookie consent, and reports every route. */
export const Analytics = () => {
  const { locale } = useLocaleCtx();
  const location = useLocation();
  const settings = useRef(null);
  const first = useRef(true);

  useEffect(() => {
    initConsentDefaults();
    let alive = true;
    const start = (s) => {
      if (!alive || !s) return;
      updateConsent({ analytics: hasAnalyticsConsent(), marketing: false });
      if (hasAnalyticsConsent()) loadGa(measurementId(s, locale));
    };
    api.get("/settings").then(({ data }) => { settings.current = data; start(data); }).catch(() => {});
    const onConsent = (e) => {
      updateConsent(e.detail || {});
      if (e.detail?.analytics) start(settings.current);
    };
    window.addEventListener("pp:consent", onConsent);
    return () => { alive = false; window.removeEventListener("pp:consent", onConsent); };
  }, [locale]);

  useEffect(() => {
    pageView(location.pathname + location.search);
    first.current = false;
  }, [location.pathname, location.search]);

  return null;
};

export default Analytics;

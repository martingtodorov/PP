import { Clock, Mail, AlertTriangle } from "lucide-react";
import { useLocaleCtx } from "../i18n/LocaleContext";

export const CONTACT_EMAIL = "contact@purepeptide.bg";

export const ContactInfo = () => {
  const { t } = useLocaleCtx();
  return (
    <section className="mt-6 space-y-5" data-testid="contact-info">
      <p className="text-base text-slate-700 leading-relaxed" data-testid="contact-intro">{t("contactIntro")}</p>

      <div className="flex gap-3 bg-amber-50 border border-amber-200 rounded-2xl p-4 sm:p-5" data-testid="contact-notice">
        <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-amber-900 leading-relaxed">
          <strong>{t("contactNoticeTitle")}:</strong> {t("contactNotice")}
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-2xl p-5" data-testid="contact-hours">
          <p className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500 font-bold">
            <Clock className="h-4 w-4 text-coral-600" /> {t("contactHours")}
          </p>
          <p className="mt-3 text-base font-semibold text-slate-900">{t("contactHoursValue")}</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl p-5" data-testid="contact-emails">
          <p className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500 font-bold">
            <Mail className="h-4 w-4 text-coral-600" /> {t("contactEmails")}
          </p>
          <p className="mt-3 text-sm text-slate-500">{t("contactGeneral")}</p>
          <a href={`mailto:${CONTACT_EMAIL}`} className="text-base font-semibold text-coral-600 hover:text-coral-700 break-all"
            data-testid="contact-general-email">{CONTACT_EMAIL}</a>
        </div>
      </div>
    </section>
  );
};

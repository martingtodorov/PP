import { useState } from "react";
import { toast } from "sonner";
import { api, formatErr } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";

const empty = { name: "", email: "", phone: "", message: "" };

export const ContactForm = () => {
  const { t, locale } = useLocaleCtx();
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const set = (k) => (e) => setForm((c) => ({ ...c, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.includes("@") || !form.message.trim()) {
      toast.error(t("contactInvalid"));
      return;
    }
    setBusy(true);
    try {
      await api.post("/contact", { ...form, locale });
      setForm(empty);
      setSent(true);
      toast.success(t("contactThanks"));
    } catch (err) { toast.error(formatErr(err)); } finally { setBusy(false); }
  };

  const field = "w-full border border-slate-300 rounded-md px-4 py-3.5 text-base outline-none focus:border-coral-500";
  return (
    <form onSubmit={submit} className="mt-8 space-y-3 max-w-xl" data-testid="contact-form">
      <h2 className="text-lg font-bold text-slate-900">{t("contactFormTitle")}</h2>
      <input value={form.name} onChange={set("name")} placeholder={t("contactName")} className={field} data-testid="contact-name" />
      <input value={form.email} onChange={set("email")} type="email" placeholder={t("contactEmailPh")} className={field} data-testid="contact-email" />
      <input value={form.phone} onChange={set("phone")} placeholder={t("contactPhone")} className={field} data-testid="contact-phone" />
      <textarea value={form.message} onChange={set("message")} placeholder={t("contactMessage")} rows={7} className={field} data-testid="contact-message" />
      <button type="submit" disabled={busy}
        className="w-full bg-coral-600 hover:bg-coral-700 text-white font-semibold py-4 rounded-md text-base disabled:opacity-60"
        data-testid="contact-submit">
        {busy ? t("contactSending") : t("contactSend")}
      </button>
      {sent && <p className="text-sm text-emerald-700" data-testid="contact-success">{t("contactSent")}</p>}
    </form>
  );
};
